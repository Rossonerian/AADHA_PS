import json
from base64 import b64encode
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest
from PIL import Image
from requests import Response
from requests.adapters import HTTPAdapter

from app.verifier import ingestion
from app.verifier.ingestion import IngestionError, ingest, redact_phone_numbers

NOW = datetime(2026, 11, 20, 12, tzinfo=UTC)
VIDEO_ID = "dQw4w9WgXcQ"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
REDACTED = "[REDACTED PHONE]"


def capture(**inputs):
    return ingest(
        **({"text": None, "url": None, "image_base64": None, "now": NOW} | inputs)
    )


@pytest.fixture(autouse=True)
def stub_http(monkeypatch):
    """Exercise Requests and the transcript library without opening any sockets."""
    calls = []

    def stub(handler):
        def send(_adapter, request, **kwargs):
            calls.append(request)
            assert kwargs["stream"] is True
            assert 0 < kwargs["timeout"][0] <= 2.0
            assert 0 < kwargs["timeout"][1] <= 2.5
            assert not kwargs["proxies"]
            status, headers, body = handler(request)
            response = Response()
            response.status_code = status
            response.headers.update(headers)
            response.encoding = "utf-8"
            response.url = request.url
            response.request = request
            response.raw = BytesIO(body)
            return response

        monkeypatch.setattr(HTTPAdapter, "send", send)
        return calls

    stub(lambda _: pytest.fail("Unexpected outbound HTTP request"))
    return stub


def test_paste_has_no_inferred_author_and_hashes_only_redacted_text():
    first = capture(
        text="  Entry  ₹187.50; target 51000-52000; call +91 98765 43210.\r\nSL 181.25.  "
    )
    second = capture(
        text="Entry  ₹187.50; target 51000-52000; call (202) 555-0123.\nSL 181.25."
    )

    expected = f"Entry  ₹187.50; target 51000-52000; call {REDACTED}.\nSL 181.25."
    assert (first.platform, first.handle, first.captured_at) == ("text", None, NOW)
    assert first.published_at is None and first.post_url is None
    assert first.text == second.text == expected
    assert (
        first.content_hash
        == second.content_hash
        == sha256(expected.encode()).hexdigest()
    )


def test_phone_redaction_matches_common_formats_without_eating_prices():
    assert redact_phone_numbers(
        "CMP 12,345.50 / SL: 12340; tgt 12345-12500; volume 100 200 300; "
        "tel 9876543210 / +44 (0)20 7123 4567 / 202.555.0123."
    ) == (
        "CMP 12,345.50 / SL: 12340; tgt 12345-12500; volume 100 200 300; "
        f"tel {REDACTED} / {REDACTED} / {REDACTED}."
    )


@pytest.mark.parametrize(
    "phone", ["98765 43210", "98765-43210", "91234-98765", "202-555-0123"]
)
def test_price_cue_does_not_persist_phone_numbers(phone):
    tip = capture(text=f"target {phone}; stop 42.5")
    expected = f"target {REDACTED}; stop 42.5"
    assert tip.text == expected
    assert tip.content_hash == sha256(expected.encode()).hexdigest()


@pytest.mark.parametrize(
    "phone", ["98765 432 10", "+91 98765\n432 10", "９８７６５ ４３２ １０"]
)
def test_split_contact_phone_is_redacted_before_hashing(phone):
    tip = capture(text=f"Entry 187.50; WhatsApp: {phone}. Target 210.")
    expected = f"Entry 187.50; WhatsApp: {REDACTED}. Target 210."
    assert (
        tip.text == expected
        and tip.content_hash == sha256(expected.encode()).hexdigest()
    )


@pytest.mark.parametrize(
    ("prefix", "handle"),
    [
        ("[20/11/26, 10:31:08 AM] Market Desk", "market desk"),
        ("20/11/26, 10:31 - \u200e+91\u202f98765 43210", None),
        ("20/11/26, 10:31 - 555-0123", None),
        ("20/11/26, 10:31 - Desk +91 98765 43210", None),
    ],
)
def test_whatsapp_export_distinguishes_names_from_phone_numbers(prefix, handle):
    tip = capture(text=f"{prefix}: Entry 187.50, target 210")
    assert (tip.platform, tip.handle) == ("whatsapp", handle)
    assert tip.text.endswith(": Entry 187.50, target 210")
    if handle is None:
        assert REDACTED in tip.text
        assert "98765" not in tip.text and "555-0123" not in tip.text


def test_whatsapp_paste_with_multiple_senders_does_not_assign_one_author():
    tip = capture(
        text="[20/11/26, 10:31] Ani: Entry 25\n[20/11/26, 10:32] Daya: Target 30"
    )
    assert (tip.platform, tip.handle) == ("whatsapp", None)


@pytest.mark.parametrize("inputs", [{}, {"text": "one", "image_base64": "image"}])
def test_ingest_requires_content_without_mixing_screenshot_and_text(inputs):
    with pytest.raises(IngestionError) as err:
        capture(**inputs)
    assert err.value.code == "INVALID_INPUT"


def test_pasted_tip_with_x_link_does_not_fetch_or_verify_author():
    tip = capture(
        text="JBM Auto 489 sl 480 intraday",
        url="https://x.com/StocksResearch/status/2123681669534404637?a=4Wp",
    )
    assert tip.text == "JBM Auto 489 sl 480 intraday"
    assert tip.post_url == "https://x.com/StocksResearch/status/2123681669534404637"
    assert tip.platform == "text"
    assert tip.handle is None and tip.published_at is None
    assert tip.author_verified is False


@pytest.mark.parametrize("url", ["bad link", "file:///etc/passwd", "https://[bad"])
def test_pasted_tip_with_malformed_link_is_rejected(url):
    with pytest.raises(IngestionError) as err:
        capture(text="A pasted tip", url=url)
    assert err.value.code == "UNSUPPORTED_URL"


def test_telegram_captures_only_requested_post_and_published_date(stub_http):
    calls = stub_http(
        lambda _: (
            200,
            {},
            b"""
        <div class="tgme_widget_message" data-post="TradeDesk/51">
          <div class="tgme_widget_message_text">Ignore the neighbouring message.</div>
          <a class="tgme_widget_message_date"><time datetime="2026-11-18T02:00:00Z"></time></a>
        </div>
        <div class="tgme_widget_message" data-post="TradeDesk/52">
          <div class="tgme_widget_message_reply"><time datetime="2026-11-17T02:00:00Z"></time></div>
          <div class="tgme_widget_message_text">Entry <b>120.25</b><br>Call +91 99887 66554</div>
          <a class="tgme_widget_message_date"><time datetime="2026-11-19T08:30:00+05:30"></time></a>
        </div>
    """,
        )
    )
    tip = capture(url="http://T.ME/TradeDesk/52/?single&phone=919876543210#part")

    assert (tip.platform, tip.handle, tip.post_url) == (
        "telegram",
        "tradedesk",
        "https://t.me/s/tradedesk/52",
    )
    assert tip.text == f"Entry 120.25\nCall {REDACTED}"
    assert tip.published_at == datetime(2026, 11, 19, 3, tzinfo=UTC)
    assert not tip.author_verified
    assert tip.captured_at == NOW
    assert [request.url for request in calls] == [tip.post_url]


def test_telegram_does_not_use_original_timestamp_for_a_known_edit(stub_http):
    stub_http(
        lambda _: (
            200,
            {},
            b"""
        <div class="tgme_widget_message" data-post="tradedesk/52">
          <div class="tgme_widget_message_edited">edited</div>
          <div class="tgme_widget_message_text">A claim in the edited text.</div>
          <a class="tgme_widget_message_date"><time datetime="2026-11-19T03:00:00Z"></time></a>
        </div>
    """,
        )
    )
    tip = capture(url="https://t.me/s/tradedesk/52")
    assert tip.published_at is None and not tip.author_verified


def test_telegram_does_not_use_other_posts_if_requested_post_is_missing(stub_http):
    stub_http(
        lambda _: (
            200,
            {},
            b"""
        <div class="tgme_widget_message" data-post="tradedesk/51">
          <div class="tgme_widget_message_text">Another post</div>
        </div>
    """,
        )
    )
    with pytest.raises(IngestionError) as err:
        capture(url="https://t.me/s/tradedesk/52")
    assert err.value.code == "TELEGRAM_UNAVAILABLE"
    assert "screenshot" in str(err.value)


def test_telegram_never_follows_a_redirect(stub_http):
    calls = stub_http(
        lambda _: (302, {"Location": "https://example.test/private"}, b"")
    )
    with pytest.raises(IngestionError) as err:
        capture(url="https://t.me/s/tradedesk/52")
    assert err.value.code == "TELEGRAM_UNAVAILABLE"
    assert len(calls) == 1


def test_telegram_rejects_oversized_responses(stub_http, monkeypatch):
    monkeypatch.setattr(ingestion, "_MAX_DOWNLOAD_BYTES", 64)
    prefix = b'<div class="tgme_widget_message" data-post="tradedesk/52">'
    stub_http(
        lambda _: (
            200,
            {},
            prefix + b'<div class="tgme_widget_message_text">Entry 12</div></div>',
        )
    )
    with pytest.raises(IngestionError) as err:
        capture(url="https://t.me/s/tradedesk/52")
    assert err.value.code == "TELEGRAM_UNAVAILABLE"


@pytest.mark.parametrize(
    "url",
    [
        "https://t.me/c/1234567/52",
        "https://t.me/+Abcdefg",
        "https://t.me/s/tradedesk",
        "https://t.me.example.test/s/tradedesk/52",
        "https://www.youtube.com@127.0.0.1/watch?v=dQw4w9WgXcQ",
        "https://private@www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com:443/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&v=abcdefghijk",
        "https://youtu.be/too-short",
        "file:///etc/secret.txt",
        "https://127.0.0.1/secret",
    ],
)
def test_unsupported_or_private_links_do_not_make_an_http_request(url):
    with pytest.raises(IngestionError) as err:
        capture(url=url)
    assert err.value.code == "UNSUPPORTED_URL"


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://x.com/trader/status/123", "X"),
        ("https://www.instagram.com/p/postcode/", "Instagram"),
        ("https://chat.whatsapp.com/private-invite", "WhatsApp"),
    ],
)
def test_unsupported_social_platforms_offer_a_fallback_without_fetching(url, platform):
    with pytest.raises(IngestionError) as err:
        capture(url=url)
    assert err.value.code == "PASTE_OR_SCREENSHOT_REQUIRED"
    assert platform in err.value.message
    assert "paste" in err.value.message and "screenshot" in err.value.message


def youtube_fixture(
    request,
    *,
    author_url,
    caption_url="https://www.youtube.com/api/timedtext?id=public",
    watch_metadata=b"",
):
    url = urlsplit(request.url)
    if url.path == "/watch":
        assert parse_qs(url.query)["v"] == [VIDEO_ID]
        return (
            200,
            {},
            b'<script>var config = {"INNERTUBE_API_KEY":"test-fixture"}</script>'
            + watch_metadata,
        )
    if url.path == "/youtubei/v1/player":
        assert request.method == "POST"
        assert json.loads(request.body)["videoId"] == VIDEO_ID
        payload = {
            "playabilityStatus": {"status": "OK"},
            "captions": {
                "playerCaptionsTracklistRenderer": {
                    "captionTracks": [
                        {
                            "baseUrl": caption_url,
                            "languageCode": "hi",
                            "name": {"runs": [{"text": "Hindi"}]},
                        }
                    ]
                }
            },
        }
        return 200, {}, json.dumps(payload).encode()
    if url.path == "/api/timedtext":
        return (
            200,
            {},
            b"""<transcript><text start="0">Entry at 515.25</text>
            <text start="3">Call 98765 43210</text></transcript>""",
        )
    if url.path == "/oembed":
        assert parse_qs(url.query)["url"] == [VIDEO_URL]
        if author_url is None:
            return 404, {}, b""
        return 200, {}, json.dumps({"author_url": author_url}).encode()
    pytest.fail("Unexpected YouTube endpoint")


@pytest.mark.parametrize(
    ("author_url", "handle"),
    [
        ("https://www.youtube.com/@MarketDesk", "@marketdesk"),
        (
            "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv",
            "UCabcdefghijklmnopqrstuv",
        ),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", None),
        ("https://www.youtube.com.example.test/@MarketDesk", None),
        (None, None),
    ],
)
def test_youtube_transcript_preserves_canonical_video_id_without_using_it_as_author(
    stub_http, author_url, handle
):
    stub_http(lambda request: youtube_fixture(request, author_url=author_url))
    tip = capture(url=f"https://youtu.be/{VIDEO_ID}?si=share&t=7")
    assert (tip.platform, tip.handle, tip.post_url) == ("youtube", handle, VIDEO_URL)
    assert tip.text == f"Entry at 515.25 Call {REDACTED}"
    assert tip.published_at is None


@pytest.mark.parametrize(
    ("watch_metadata", "expected"),
    [
        (
            (
                b'<meta itemprop="uploadDate" content="2026-11-17">'
                b'<meta itemprop="datePublished" content="2026-11-19T08:30:00+05:30">'
            ),
            datetime(2026, 11, 19, 3, tzinfo=UTC),
        ),
        (
            (
                b'<meta itemprop="datePublished" content="not-a-date">'
                b'<meta itemprop="uploadDate" content="2026-11-18">'
            ),
            datetime(2026, 11, 18, tzinfo=UTC),
        ),
        (
            (
                b'<meta itemprop="datePublished" content="2026-11-19T08:30:00">'
                b'<meta itemprop="dateModified" content="2026-11-19T08:30:00Z">'
            ),
            None,
        ),
    ],
)
def test_youtube_publication_uses_only_metadata_from_the_existing_watch_request(
    stub_http, watch_metadata, expected
):
    calls = stub_http(
        lambda request: youtube_fixture(
            request, author_url=None, watch_metadata=watch_metadata
        )
    )
    tip = capture(url=VIDEO_URL)

    assert tip.published_at == expected
    assert tip.captured_at == NOW
    assert [urlsplit(request.url).path for request in calls] == [
        "/watch",
        "/youtubei/v1/player",
        "/api/timedtext",
        "/oembed",
    ]


@pytest.mark.parametrize(
    "caption_url",
    [
        "http://169.254.169.254/api/timedtext",
        "https://www.youtube.com/redirect?q=https://example.test/api/timedtext",
    ],
)
def test_youtube_rejects_unapproved_provider_generated_caption_urls(
    stub_http, caption_url
):
    calls = stub_http(
        lambda request: youtube_fixture(
            request, author_url=None, caption_url=caption_url
        )
    )
    with pytest.raises(IngestionError) as err:
        capture(url=VIDEO_URL)
    assert err.value.code == "YOUTUBE_TRANSCRIPT_UNAVAILABLE"
    assert "paste" in err.value.message.lower()
    assert [urlsplit(request.url).path for request in calls] == [
        "/watch",
        "/youtubei/v1/player",
    ]


def test_youtube_denial_is_not_bypassed(stub_http):
    def private_video(request):
        if urlsplit(request.url).path == "/watch":
            return 200, {}, b'{"INNERTUBE_API_KEY":"test-fixture"}'
        assert urlsplit(request.url).path == "/youtubei/v1/player"
        return (
            200,
            {},
            b'{"playabilityStatus":{"status":"LOGIN_REQUIRED","reason":"Private video"}}',
        )

    calls = stub_http(private_video)
    with pytest.raises(IngestionError) as err:
        capture(url=VIDEO_URL)
    assert err.value.code == "YOUTUBE_TRANSCRIPT_UNAVAILABLE"
    assert len(calls) == 2


def png_base64(size=(180, 100)):
    with Image.new("RGBA", size, "white") as image, BytesIO() as buffer:
        image.save(buffer, format="PNG")
        return b64encode(buffer.getvalue()).decode("ascii")


def test_screenshot_ocr_redacts_before_hashing_without_guessing_author(monkeypatch):
    def ocr(image):
        assert image.size == (180, 100) and image.mode == "RGB"
        rows = [
            (None, "Entry 320.50", 0.98),
            (None, "Call +91 98765", 0.95),
            (None, "43210", 0.90),
        ]
        return rows, None

    monkeypatch.setattr(ingestion, "_ocr_engine", lambda: ocr)
    tip = capture(image_base64=f"data:image/png;base64,{png_base64()}")
    assert (tip.platform, tip.handle) == ("screenshot", None)
    expected = f"Entry 320.50\nCall {REDACTED}"
    assert tip.text == expected
    assert tip.content_hash == sha256(expected.encode()).hexdigest()


def test_screenshot_without_recognised_text_suggests_fallback(monkeypatch):
    monkeypatch.setattr(ingestion, "_ocr_engine", lambda: lambda _: (None, None))
    with pytest.raises(IngestionError) as err:
        capture(image_base64=png_base64())
    assert err.value.code == "NO_TEXT"
    assert "screenshot" in err.value.message


@pytest.mark.parametrize(
    "image_base64", ["not base64===", "\u03b1", b64encode(b"not an image").decode()]
)
def test_invalid_screenshot_does_not_reach_ocr(image_base64, monkeypatch):
    monkeypatch.setattr(
        ingestion, "_ocr_engine", lambda: pytest.fail("Invalid image reached OCR")
    )
    with pytest.raises(IngestionError) as err:
        capture(image_base64=image_base64)
    assert err.value.code == "INVALID_IMAGE"


def test_screenshots_have_separate_encoded_size_and_pixel_limits(monkeypatch):
    monkeypatch.setattr(
        ingestion, "_ocr_engine", lambda: pytest.fail("Oversized image reached OCR")
    )
    encoded = png_base64()
    with monkeypatch.context() as patch:
        patch.setattr(ingestion, "_MAX_BASE64_CHARS", len(encoded) - 1)
        with pytest.raises(IngestionError) as err:
            capture(image_base64=encoded)
        assert err.value.code == "IMAGE_TOO_LARGE"
    monkeypatch.setattr(ingestion, "_MAX_PIXELS", 180 * 100 - 1)
    with pytest.raises(IngestionError) as err:
        capture(image_base64=encoded)
    assert err.value.code == "IMAGE_TOO_LARGE"
