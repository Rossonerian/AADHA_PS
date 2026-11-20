"""Capture public tips or user-provided content without retaining phone numbers or images."""

import re
from base64 import b64decode
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from hashlib import sha256
from io import BytesIO
from threading import Lock
from time import monotonic
from typing import Any
from urllib.parse import SplitResult, parse_qs, unquote, urlsplit
from xml.etree.ElementTree import ParseError

import requests
from bs4 import BeautifulSoup, ParserRejectedMarkup, SoupStrainer
from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]
from PIL import Image, ImageOps
from youtube_transcript_api import (
    NoTranscriptFound,
    YouTubeTranscriptApi,
    YouTubeTranscriptApiException,
)


@dataclass(frozen=True, slots=True)
class CapturedTip:
    text: str
    platform: str
    handle: str | None
    content_hash: str
    captured_at: datetime
    published_at: datetime | None = None
    post_url: str | None = None
    author_verified: bool = False


class IngestionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_MAX_TEXT_CHARS = 20_000
_MAX_URL_CHARS = 2_048
_MAX_BASE64_CHARS = 8_000_000  # At most 6 MB decoded, including data URI overhead.
_MAX_PIXELS = 12_000_000
_MAX_IMAGE_SIDE = 8_192
_MAX_DOWNLOAD_BYTES = 4 * 1024 * 1024
_NETWORK_BUDGET_SECONDS = 8.0
_TELEGRAM_HOST = "t.me"
_YOUTUBE_HOST = "www.youtube.com"
_YOUTUBE_HOSTS = frozenset({"youtube.com", _YOUTUBE_HOST, "m.youtube.com"})
_YOUTUBE_REQUESTS = frozenset(
    {
        ("GET", "/watch"),
        ("GET", "/api/timedtext"),
        ("GET", "/oembed"),
        ("POST", "/youtubei/v1/player"),
    }
)
_PASTE_ONLY_HOSTS = {
    "x.com": "X",
    "www.x.com": "X",
    "mobile.x.com": "X",
    "twitter.com": "X",
    "www.twitter.com": "X",
    "mobile.twitter.com": "X",
    "instagram.com": "Instagram",
    "www.instagram.com": "Instagram",
    "m.instagram.com": "Instagram",
    "instagr.am": "Instagram",
    "whatsapp.com": "WhatsApp",
    "www.whatsapp.com": "WhatsApp",
    "web.whatsapp.com": "WhatsApp",
    "api.whatsapp.com": "WhatsApp",
    "chat.whatsapp.com": "WhatsApp",
    "wa.me": "WhatsApp",
}
_TELEGRAM_POST = re.compile(
    r"/(?:s/)?([a-z][a-z0-9_]{3,31})/([1-9][0-9]{0,9})/?", re.IGNORECASE | re.ASCII
)
_TELEGRAM_RESERVED = frozenset(
    {"addlist", "addstickers", "boost", "joinchat", "login", "proxy", "share", "socks"}
)
_YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_YOUTUBE_CHANNEL_ID = re.compile(r"/channel/(UC[A-Za-z0-9_-]{22})/?")
_YOUTUBE_HANDLE = re.compile(r"/(@[\w.-]{3,30})/?")
_IMAGE_DATA_HEADER = re.compile(r"data:image/(?:png|jpe?g|webp);base64", re.IGNORECASE)
_OCR_LOCK = Lock()

# Match common dialling formats, not arbitrary runs of short numbers, which are
# often adjacent price levels. Dot separators are limited to the 3.3.4 format.
_PHONE_MARKER = "[REDACTED PHONE]"
_PHONE_SEP = r"[\t \u00a0\u2007\u202f\-\u2010\u2011\u2013]"
_PHONE_PREFIX = r"(?:\+|00)\d{1,3}"
_LOCAL_PHONE = rf"""
    \(\d{{2,5}}\){_PHONE_SEP}?\d{{3,5}}{_PHONE_SEP}?\d{{3,5}}
    | \d{{5}}{_PHONE_SEP}\d{{5}}
    | \d{{4}}{_PHONE_SEP}\d{{3}}{_PHONE_SEP}\d{{3}}
    | \d{{3}}{_PHONE_SEP}\d{{3}}{_PHONE_SEP}\d{{4}}
    | \d{{4}}{_PHONE_SEP}\d{{6,7}}
    | \d{{2}}{_PHONE_SEP}\d{{4}}{_PHONE_SEP}\d{{4}}
    | \d{{3}}\.\d{{3}}\.\d{{4}}
    | \d{{10,15}}
"""
_PHONE_NUMBER = re.compile(
    rf"(?<![\w.])(?:{_PHONE_PREFIX}{_PHONE_SEP}\d{{5}}\n[ \t]*\d{{5}}"
    rf"|(?:{_PHONE_PREFIX}{_PHONE_SEP}?(?:\(0\){_PHONE_SEP}?)?)?(?:{_LOCAL_PHONE})"
    rf"|(?:\+|00)\d(?:{_PHONE_SEP}?\d){{7,14}})(?!\w|\.\d)",
    re.VERBOSE,
)
_CONTACT_PHONE = re.compile(
    r"(?P<cue>\b(?:whats[\s-]*app|call|phone|tel(?:ephone)?|mobile|contact|text|sms)"
    r"(?:\s+(?:me|us|number|no\.?|at|on)){0,3}[ \t]*[:=@#-]?[ \t\n]*)"
    r"[+＋]?\s*\(?\d(?:[\s().\-\u2010\u2011\u2013]{0,4}\d){7,14}(?!\w|[\s().\-\u2010\u2011\u2013]*\d)",
    re.IGNORECASE,
)
_PRICE_CUE = re.compile(
    r"(?:[\u20b9$\u20ac\u00a3]|\b(?:rs\.?|inr|entry|target|tgt|stop(?:\s+loss)?|sl|cmp|price|levels?|range|above|below)"
    r"\s*[:=@]?)\s*$",
    re.IGNORECASE,
)
_PRICE_RANGE = re.compile(r"(\d{5})[-\u2010\u2011\u2013](\d{5})")
_TIMESTAMP = (
    r"(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2}),?[^\S\n]+"
    r"\d{1,2}:\d{2}(?::\d{2})?(?:[^\S\n]*[ap]m)?"
)
_WHATSAPP_HEADER = re.compile(
    rf"^(?:\[{_TIMESTAMP}\][^\S\n]*|{_TIMESTAMP}[^\S\n]+-[^\S\n]+)(?P<sender>[^:\n]{{1,120}}):",
    re.IGNORECASE | re.MULTILINE,
)
_NUMERIC_SENDER = re.compile(r"[+\d().~\s\-\u2010\u2011\u2013]+")
_INVISIBLE_MARKS = dict.fromkeys(
    map(
        ord,
        "\u061c\u200b\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2060\u2066\u2067\u2068\u2069\ufeff",
    ),
)


def redact_phone_numbers(text: str) -> str:
    """Remove likely phone numbers, including number-only WhatsApp sender labels."""
    text = text.translate(_INVISIBLE_MARKS)

    def redact_sender(match: re.Match[str]) -> str:
        sender = match["sender"]
        if _NUMERIC_SENDER.fullmatch(sender) and any(ch.isdecimal() for ch in sender):
            return f"{match[0][:-len(sender) - 1]}{_PHONE_MARKER}:"
        return match[0]

    text = _WHATSAPP_HEADER.sub(redact_sender, text)
    text = _CONTACT_PHONE.sub(lambda match: f"{match['cue']}{_PHONE_MARKER}", text)

    def redact(match: re.Match[str]) -> str:
        number = match[0]
        before = text[max(0, match.start() - 32) : match.start()]
        # Preserve plausible stock ranges only when they do not also look
        # like an Indian mobile number (national format starts with 6–9).
        if (prices := _PRICE_RANGE.fullmatch(number)) and _PRICE_CUE.search(before):
            low, high = map(int, prices.groups())
            if 0 < low < 60_000 and low < high and 5 * high <= 6 * low:
                return number
        return _PHONE_MARKER

    return _PHONE_NUMBER.sub(redact, text)


def _whatsapp_source(text: str, default_platform: str) -> tuple[str, str | None]:
    senders = {
        " ".join(match["sender"].lstrip("~ ").split()).casefold()
        for match in _WHATSAPP_HEADER.finditer(text)
    }
    if not senders:
        return default_platform, None
    if len(senders) != 1:
        return "whatsapp", None
    sender = senders.pop()
    if not any(ch.isalpha() for ch in sender) or _PHONE_MARKER.casefold() in sender:
        return "whatsapp", None
    return "whatsapp", sender


def _split_url(url: str, *, limit: int = _MAX_URL_CHARS) -> SplitResult:
    if (
        len(url) > limit
        or "\\" in url
        or any(ch.isspace() or ord(ch) < 33 or ord(ch) == 127 for ch in url)
    ):
        raise ValueError("Invalid URL")
    return urlsplit(url)


class _PublicSession(requests.Session):
    """Only the configured public HTTPS origin, including URLs supplied by providers."""

    def __init__(self, host: str) -> None:
        super().__init__()
        self._host = host
        self._deadline = monotonic() + _NETWORK_BUDGET_SECONDS
        self.trust_env = False  # Do not inherit proxies or netrc authentication.

    def get_redirect_target(self, resp: requests.Response) -> None:
        # Requests otherwise resolves and buffers the redirect body for Response.next.
        return None

    def prepare_request(self, request: requests.Request) -> requests.PreparedRequest:
        url = request.url
        if not isinstance(url, str):
            raise requests.RequestException("Invalid provider URL")
        self._validate_target(request.method, url)
        return super().prepare_request(request)

    def _validate_target(self, method: str | None, url: str) -> None:
        try:
            parsed = _split_url(url, limit=8_192)
        except ValueError:
            raise requests.RequestException("Invalid provider URL") from None
        if parsed.scheme != "https" or parsed.netloc.lower() != self._host:
            raise requests.RequestException("Unapproved provider origin")
        if (
            self._host == _YOUTUBE_HOST
            and (method, parsed.path) not in _YOUTUBE_REQUESTS
        ):
            raise requests.RequestException("Unapproved YouTube endpoint")

    def send(
        self, request: requests.PreparedRequest, **kwargs: Any
    ) -> requests.Response:
        if request.url is None:
            raise requests.RequestException("Invalid provider URL")
        self._validate_target(request.method, request.url)
        remaining = self._deadline - monotonic()
        if remaining <= 0:
            raise requests.Timeout("Provider time limit exceeded")
        kwargs.update(
            allow_redirects=False,
            stream=True,
            timeout=(min(2.0, remaining), min(2.5, remaining)),
        )
        with super().send(request, **kwargs) as response:
            if response.status_code != 200:
                raise requests.RequestException(
                    "Provider did not return public content"
                )
            with BytesIO() as body:
                for chunk in response.iter_content(16_384):
                    if monotonic() >= self._deadline:
                        raise requests.Timeout("Provider time limit exceeded")
                    if body.tell() + len(chunk) > _MAX_DOWNLOAD_BYTES:
                        raise requests.RequestException(
                            "Provider response exceeds the size limit"
                        )
                    body.write(chunk)
                # iter_content exhausts the stream; cache those bytes for the transcript library.
                response._content = body.getvalue()
            return response


class _YouTubeSession(_PublicSession):
    def __init__(self, watch_url: str) -> None:
        super().__init__(_YOUTUBE_HOST)
        self._watch_url = watch_url
        self.watch_html: bytes | None = None

    def send(
        self, request: requests.PreparedRequest, **kwargs: Any
    ) -> requests.Response:
        response = super().send(request, **kwargs)
        if request.method == "GET" and request.url == self._watch_url:
            self.watch_html = response.content
        return response


def _telegram_post(
    handle: str, post_id: str, post_url: str
) -> tuple[str, datetime | None, bool]:
    unavailable = (
        "The public Telegram post could not be read. "
        "Paste its text or upload a screenshot."
    )
    try:
        with _PublicSession(_TELEGRAM_HOST) as client:
            page = BeautifulSoup(client.get(post_url).content, "html.parser")
    except requests.RequestException:
        raise IngestionError("TELEGRAM_UNAVAILABLE", unavailable) from None
    wanted = f"{handle}/{post_id}"

    def matches_post(value: str | None) -> bool:
        return value is not None and value.lower() == wanted

    post = page.find(
        None, attrs={"data-post": matches_post}, class_="tgme_widget_message"
    )
    if post is None:
        raise IngestionError("TELEGRAM_UNAVAILABLE", unavailable)
    body = post.select_one(".tgme_widget_message_text")
    if body is None:
        raise IngestionError("TELEGRAM_UNAVAILABLE", unavailable)
    for line_break in body.find_all("br"):
        line_break.replace_with("\n")
    text = body.get_text().strip()
    if not text:
        raise IngestionError("TELEGRAM_UNAVAILABLE", unavailable)
    # A forwarded or replied-to quote is not evidence that this channel made the call.
    own_message = (
        post.select_one(
            ".tgme_widget_message_forwarded_from, .tgme_widget_message_reply, blockquote"
        )
        is None
    )
    published_at = None
    stamp = post.select_one(".tgme_widget_message_date time[datetime]")
    if (
        post.select_one(".tgme_widget_message_edited, .tgme_widget_message_edit")
        is not None
    ):
        return (
            text,
            None,
            False,
        )  # Original publication time does not identify the edited text.
    if stamp is not None:
        value = stamp.get("datetime")
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is not None:
                    published_at = parsed.astimezone(UTC)
            except (ValueError, OverflowError):
                pass
    return text, published_at, own_message


def _youtube_publication_date(html: bytes | None) -> datetime | None:
    if not html:
        return None
    fields = ("datePublished", "uploadDate")
    try:
        metadata = BeautifulSoup(
            html, "html.parser", parse_only=SoupStrainer("meta", itemprop=fields)
        )
    except ParserRejectedMarkup:
        return None
    for field in fields:
        for tag in metadata.find_all("meta", itemprop=field):
            value = tag.get("content")
            if not isinstance(value, str):
                continue
            value = value.strip()
            try:
                published_at = datetime.fromisoformat(value)
                if published_at.tzinfo is not None:
                    return published_at.astimezone(UTC)
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    # Date-only evidence has no time; UTC midnight represents that date.
                    return published_at.replace(tzinfo=UTC)
            except (ValueError, OverflowError):
                continue
    return None


def _youtube_author(client: _PublicSession, post_url: str) -> str | None:
    try:
        metadata = client.get(
            f"https://{_YOUTUBE_HOST}/oembed",
            params={"url": post_url, "format": "json"},
        ).json()
        author_url = metadata.get("author_url") if isinstance(metadata, dict) else None
        if not isinstance(author_url, str):
            return None
        author = _split_url(author_url)
    except (requests.RequestException, ValueError):
        return None
    if author.scheme != "https" or author.netloc.lower() not in _YOUTUBE_HOSTS:
        return None
    if channel := _YOUTUBE_CHANNEL_ID.fullmatch(author.path):
        return channel[1]
    if handle := _YOUTUBE_HANDLE.fullmatch(unquote(author.path)):
        result = handle[1]
        if redact_phone_numbers(result) == result and any(
            ch.isalpha() for ch in result
        ):
            return result.casefold()
    return None


def _youtube_transcript(
    video_id: str, post_url: str
) -> tuple[str, str | None, datetime | None]:
    unavailable = (
        "No accessible YouTube transcript. Paste the transcript or upload a screenshot."
    )
    with _YouTubeSession(post_url) as client:
        try:
            tracks = YouTubeTranscriptApi(http_client=client).list(video_id)
            try:
                selected = tracks.find_transcript(("en", "en-IN", "hi", "hi-IN"))
            except NoTranscriptFound:
                alternative = next(iter(tracks), None)
                if alternative is None:
                    raise
                selected = alternative
            text = " ".join(snippet.text for snippet in selected.fetch()).strip()
        except (
            YouTubeTranscriptApiException,
            requests.RequestException,
            DefusedXmlException,
            ParseError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
        ):
            raise IngestionError(
                "YOUTUBE_TRANSCRIPT_UNAVAILABLE", unavailable
            ) from None
        if not text:
            raise IngestionError("YOUTUBE_TRANSCRIPT_UNAVAILABLE", unavailable)
        author = _youtube_author(client, post_url)
        return text, author, _youtube_publication_date(client.watch_html)


def _video_id(url: SplitResult) -> str | None:
    path = url.path.rstrip("/")
    if url.netloc.lower() == "youtu.be":
        candidate = path.removeprefix("/")
    elif path == "/watch":
        ids = parse_qs(url.query, keep_blank_values=True).get("v", [])
        candidate = ids[0] if len(ids) == 1 else ""
    else:
        match = re.fullmatch(r"/(?:shorts|live|embed)/([^/]+)", path)
        candidate = match[1] if match else ""
    return candidate if _YOUTUBE_ID.fullmatch(candidate) else None


@cache
def _ocr_engine() -> Any:
    from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-untyped]

    # The 1.4.4 wheel bundles ONNX models; no network or local temp files.
    return RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)


def _read_ocr(image: Image.Image) -> str:
    try:
        with _OCR_LOCK:
            rows, _ = _ocr_engine()(image)
        return "\n".join(row[1] for row in rows) if rows else ""
    except (
        Exception
    ):  # noqa: BLE001 - OpenCV and ONNX runtime errors have no shared library base.
        raise IngestionError(
            "OCR_FAILED", "The screenshot could not be read. Paste its text instead."
        ) from None


def _image_text(encoded: str) -> str:
    invalid = "Upload a base64-encoded PNG, JPEG or WebP screenshot."
    too_large = "The screenshot is too large. Crop it and try again."
    if len(encoded) > _MAX_BASE64_CHARS:
        raise IngestionError("IMAGE_TOO_LARGE", too_large)
    if encoded[:5].lower() == "data:":
        header, separator, encoded = encoded.partition(",")
        if not separator or not _IMAGE_DATA_HEADER.fullmatch(header):
            raise IngestionError("INVALID_IMAGE", invalid)
    try:
        raw = b64decode(encoded, validate=True)
    except ValueError:
        raise IngestionError("INVALID_IMAGE", invalid) from None
    try:
        with Image.open(BytesIO(raw), formats=("PNG", "JPEG", "WEBP")) as image:
            width, height = image.size
            if width * height > _MAX_PIXELS or max(width, height) > _MAX_IMAGE_SIDE:
                raise IngestionError("IMAGE_TOO_LARGE", too_large)
            if (
                getattr(image, "is_animated", False)
                or max(width, height) > min(width, height) * 60
            ):
                raise IngestionError("INVALID_IMAGE", invalid)
            ImageOps.exif_transpose(image, in_place=True)
            if image.mode == "RGB":
                return _read_ocr(image)
            with image.convert("RGB") as rgb:
                return _read_ocr(rgb)
    except Image.DecompressionBombError:
        raise IngestionError("IMAGE_TOO_LARGE", too_large) from None
    except IngestionError:
        raise
    except (ValueError, OSError, SyntaxError):
        raise IngestionError("INVALID_IMAGE", invalid) from None


def ingest(
    *,
    text: str | None,
    url: str | None,
    image_base64: str | None,
    now: datetime | None = None,
) -> CapturedTip:
    """Capture exactly one input; hash the redacted text, not the URL or source metadata."""
    if sum(value is not None for value in (text, url, image_base64)) != 1:
        raise IngestionError(
            "INVALID_INPUT", "Provide exactly one link, pasted tip or screenshot."
        )
    captured_at = now if now is not None else datetime.now(UTC)
    captured_at = (
        captured_at.replace(tzinfo=UTC)
        if captured_at.tzinfo is None
        else captured_at.astimezone(UTC)
    )
    published_at = post_url = handle = None
    author_verified = False
    if url is not None:
        unsupported = (
            "Use a public Telegram post or YouTube video link, "
            "or paste the tip or upload a screenshot."
        )
        try:
            link = _split_url(url.strip())
        except ValueError:
            raise IngestionError("UNSUPPORTED_URL", unsupported) from None
        host = link.netloc.lower()
        if link.scheme not in {"http", "https"}:
            raise IngestionError("UNSUPPORTED_URL", unsupported)
        if service := _PASTE_ONLY_HOSTS.get(host):
            raise IngestionError(
                "PASTE_OR_SCREENSHOT_REQUIRED",
                f"For {service}, paste the tip or upload a screenshot.",
            )
        if host == _TELEGRAM_HOST:
            post = _TELEGRAM_POST.fullmatch(link.path)
            if post is None or post[1].lower() in _TELEGRAM_RESERVED:
                raise IngestionError("UNSUPPORTED_URL", unsupported)
            handle, post_id = post[1].lower(), post[2]
            platform = "telegram"
            post_url = f"https://{_TELEGRAM_HOST}/s/{handle}/{post_id}"
            text, published_at, author_verified = _telegram_post(
                handle, post_id, post_url
            )
        elif host in _YOUTUBE_HOSTS or host == "youtu.be":
            video_id = _video_id(link)
            if video_id is None:
                raise IngestionError("UNSUPPORTED_URL", unsupported)
            platform = "youtube"
            post_url = f"https://{_YOUTUBE_HOST}/watch?v={video_id}"
            text, handle, published_at = _youtube_transcript(video_id, post_url)
        else:
            raise IngestionError("UNSUPPORTED_URL", unsupported)
    elif image_base64 is not None:
        platform = "screenshot"
        text = _image_text(image_base64)
    else:
        platform = "text"
        if text is not None and len(text) > _MAX_TEXT_CHARS:
            raise IngestionError("INVALID_INPUT", "The pasted tip is too long.")

    assert text is not None
    text = redact_phone_numbers(text.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not text:
        raise IngestionError(
            "NO_TEXT",
            "No text was found. Paste the tip or upload a clearer screenshot.",
        )
    if platform in {"text", "screenshot"}:
        platform, handle = _whatsapp_source(text, platform)
    return CapturedTip(
        text,
        platform,
        handle,
        sha256(text.encode("utf-8")).hexdigest(),
        captured_at,
        published_at,
        post_url,
        author_verified,
    )
