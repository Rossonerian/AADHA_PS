"""Provider boundaries: no network, safe errors, limits, cache and verbatim data."""

import json

import httpx
import pytest
import respx
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.transcribe import TranscriptionError, transcribe
from app.core.web_search import SearchError, _cache, web_search

VIDEO = "https://www.youtube.com/watch?v=abcdefghijk"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/interactions"
EXA = "https://api.exa.ai/search"


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    monkeypatch.setenv("WEB_SEARCH_API_KEY", "fixture-search-key")
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "exa")
    get_settings.cache_clear()
    _cache.clear()
    yield
    get_settings.cache_clear()
    _cache.clear()


def watch(*, duration=120, private=False):
    return (
        "var ytInitialPlayerResponse = "
        + json.dumps(
            {
                "videoDetails": {"lengthSeconds": str(duration)},
                "microformat": {"playerMicroformatRenderer": {"isUnlisted": private}},
                "playabilityStatus": {"status": "OK"},
            }
        )
        + ";"
    )


def generated():
    return {
        "steps": [
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "segments": [
                                    {
                                        "start_s": 1,
                                        "end_s": 8,
                                        "text": "TCS will rise. Target 140; stop 90.",
                                    }
                                ],
                                "language": "en",
                                "data_origin": "real",
                            }
                        ),
                    }
                ]
            }
        ]
    }


@respx.mock
def test_transcription_keeps_words_and_timestamps_and_uses_schema():
    respx.get(VIDEO).respond(text=watch())
    route = respx.post(GEMINI).respond(json=generated())
    transcript = transcribe(VIDEO)
    assert transcript.segments[0].text == "TCS will rise. Target 140; stop 90."
    assert transcript.segments[0].start_s == 1
    payload = json.loads(route.calls[0].request.content)
    assert payload["store"] is False
    assert "verbatim" in payload["input"][1]["text"]
    assert payload["response_format"]["schema"]["properties"]["segments"]


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/secret",
        "file:///secret",
        VIDEO + "&other=x",
        "https://youtube.com@localhost/watch?v=abcdefghijk",
    ],
)
@respx.mock
def test_transcription_rejects_noncanonical_input_without_requests(url):
    with pytest.raises(TranscriptionError, match="unavailable"):
        transcribe(url)
    assert not respx.calls


@pytest.mark.parametrize(
    "page", [watch(duration=1801), watch(private=True), "unknown duration"]
)
@respx.mock
def test_transcription_rejects_unknown_or_unbounded_media(page):
    respx.get(VIDEO).respond(text=page)
    route = respx.post(GEMINI)
    with pytest.raises(TranscriptionError):
        transcribe(VIDEO)
    assert not route.called


@pytest.mark.parametrize("failure", ["timeout", "limit", "payload"])
@respx.mock
def test_transcription_provider_failure_is_typed_and_private(failure):
    respx.get(VIDEO).respond(text=watch())
    route = respx.post(GEMINI)
    if failure == "timeout":
        route.side_effect = httpx.ReadTimeout("sensitive provider body")
    elif failure == "limit":
        route.respond(429, text="sensitive provider body")
    else:
        route.respond(json={"steps": []})
    with pytest.raises(TranscriptionError) as error:
        transcribe(VIDEO)
    assert "sensitive" not in str(error.value)
    assert route.call_count == (1 if failure == "payload" else 3)


@respx.mock
def test_search_cache_is_24_hours_defensive_and_does_not_invent_publication(
    monkeypatch,
):
    import app.core.web_search as module

    clock = [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    route = respx.post(EXA).respond(
        json={
            "results": [
                {
                    "url": "https://example.org/post",
                    "title": "Discussion",
                    "text": "Page text",
                },
                {
                    "url": "https://example.org/dated",
                    "title": "Dated discussion",
                    "text": "Page text",
                    "publishedDate": "2024-01-01T00:00:00Z",
                },
            ]
        }
    )
    first = web_search('"desk" "telegram"', limit=3)
    assert first[0].published_at is None
    assert first[1].published_at.year == 2024
    first[0].title = "mutated"
    clock[0] = 86399
    assert web_search('"desk" "telegram"', limit=3)[0].title == "Discussion"
    assert route.call_count == 1
    clock[0] = 86401
    web_search('"desk" "telegram"', limit=3)
    assert route.call_count == 2


@pytest.mark.parametrize("failure", ["timeout", "limit", "payload"])
@respx.mock
def test_search_failure_is_typed_and_not_cached(failure):
    route = respx.post(EXA)
    if failure == "timeout":
        route.side_effect = httpx.ReadTimeout("provider details")
    elif failure == "limit":
        route.respond(429, text="provider details")
    else:
        route.respond(json={"results": "wrong"})
    with pytest.raises(SearchError) as error:
        web_search("fixture desk", limit=2)
    assert "provider details" not in str(error.value)
    assert not _cache


def test_config_cannot_silently_enable_an_invalid_weight():
    for weight in (-1, 11):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, tip_quality_weight=weight)
    assert Settings(_env_file=None).tip_quality_weight == 0
