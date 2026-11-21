"""Tavily web search; cached excerpts are display evidence, never rating inputs."""

import hashlib
from collections import OrderedDict
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from threading import Lock
from time import monotonic
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.errors import AppError


class SearchError(AppError):
    def __init__(self, code: str = "SEARCH_UNAVAILABLE") -> None:
        super().__init__(code, "Public search links are temporarily unavailable.", 503)


def _retryable(error: BaseException) -> bool:
    return isinstance(error, (httpx.TimeoutException, httpx.TransportError)) or (
        isinstance(error, httpx.HTTPStatusError)
        and (error.response.status_code == 429 or error.response.status_code >= 500)
    )


class SearchResult(BaseModel):
    url: HttpUrl
    title: str = Field(min_length=1, max_length=1000)
    published_at: datetime | None = None
    snippet: str = Field(default="", max_length=4000)
    data_origin: Literal["real", "synthetic"] = "real"


_cache: OrderedDict[tuple[str, str, int], tuple[float, list[SearchResult]]] = (
    OrderedDict()
)
_lock = Lock()


def _published_at(value: object) -> datetime | None:
    """Accept provider ISO/RFC dates; never infer a date from a snippet."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip())
    except ValueError:
        try:
            result = parsedate_to_datetime(value.strip())
        except (ValueError, TypeError, OverflowError):
            return None
    return (
        result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)
    )


def web_search(query: str, *, limit: int = 5) -> list[SearchResult]:
    """One adapter. Preserve Tavily published_date; unknown dates remain null."""
    if not query.strip() or len(query) > 600 or not 1 <= limit <= 20:
        raise SearchError("INVALID_SEARCH")
    settings = get_settings()
    api_key = settings.tavily_api_key or settings.web_search_api_key
    if settings.web_search_provider != "tavily" or not api_key:
        raise SearchError("SEARCH_NOT_CONFIGURED")
    key = (
        hashlib.sha256(api_key.encode()).hexdigest(),
        query,
        limit,
    )
    with _lock:
        cached = _cache.get(key)
        if cached and cached[0] > monotonic():
            return [r.model_copy(deep=True) for r in cached[1]]
    try:
        with httpx.Client(
            timeout=10, follow_redirects=False, trust_env=False
        ) as client:
            for attempt in Retrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.2, max=2),
                retry=retry_if_exception(_retryable),
                reraise=True,
            ):
                with (
                    attempt,
                    client.stream(
                        "POST",
                        "https://api.tavily.com/search",
                        json={
                            "query": query,
                            "max_results": limit,
                            "topic": "general",
                            "search_depth": "basic",
                            "include_published_date": True,
                            "include_answer": False,
                            "include_raw_content": False,
                            "include_images": False,
                            "auto_parameters": False,
                        },
                        headers={"Authorization": f"Bearer {api_key}"},
                    ) as response,
                ):
                    response.raise_for_status()
                    data = bytearray()
                    for part in response.iter_bytes():
                        data.extend(part)
                        if len(data) > 1_000_000:
                            raise SearchError("INVALID_SEARCH_RESPONSE")
                    import json

                    body = json.loads(data)
                    rows = body["results"]
                    if not isinstance(rows, list):
                        raise SearchError("INVALID_SEARCH_RESPONSE")
                    results = []
                    for row in rows[:limit]:
                        url = row["url"]
                        parsed = urlsplit(url)
                        if (
                            parsed.scheme != "https"
                            or parsed.username
                            or parsed.password
                        ):
                            continue
                        # A provider-stated publication timestamp is optional, never inferred.
                        results.append(
                            SearchResult(
                                url=url,
                                title=row["title"],
                                snippet=(row.get("content") or "")[:4000],
                                published_at=_published_at(row.get("published_date")),
                            )
                        )
        with _lock:
            _cache[key] = (monotonic() + 86400, results)
            _cache.move_to_end(key)
            while len(_cache) > 256:
                _cache.popitem(last=False)
        return [r.model_copy(deep=True) for r in results]
    except httpx.HTTPStatusError as exc:
        raise SearchError(
            "SEARCH_RATE_LIMITED"
            if exc.response.status_code == 429
            else (
                "SEARCH_QUOTA_EXCEEDED"
                if exc.response.status_code in (432, 433)
                else "SEARCH_UNAVAILABLE"
            )
        ) from None
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ValidationError,
    ):
        raise SearchError("INVALID_SEARCH_RESPONSE") from None
