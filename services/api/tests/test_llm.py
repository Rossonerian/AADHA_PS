"""Unit tests for the OpenRouter LLM client (`app.core.llm`)."""

from __future__ import annotations

import io
import json
import logging
from typing import Any

import httpx
import pytest
import respx
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import ConfigurationError, ExternalServiceError
from app.core.llm import acomplete, complete, get_usage_summary, reset_usage_summary
from app.core.logging import get_logger


class ClaimExtraction(BaseModel):
    symbol: str
    direction: str
    confidence: float


@pytest.fixture(autouse=True)
def _clean_env_and_usage(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key-123")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "google/gemini-2.0-flash-001")
    get_settings.cache_clear()
    reset_usage_summary()
    yield
    get_settings.cache_clear()
    reset_usage_summary()


@respx.mock
def test_complete_plain_text_and_usage_summary() -> None:
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Free cash flow measures cash.",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 30,
                    "total_tokens": 150,
                    "cost": 0.00024,
                },
            },
        )
    )

    log_buffer = io.StringIO()
    llm_logger = get_logger("core.llm")
    stream_handler = next(
        h for h in llm_logger.handlers if isinstance(h, logging.StreamHandler)
    )
    prev_stream = stream_handler.setStream(log_buffer)
    try:
        result = complete("Explain free cash flow briefly.", system="Be concise.")
    finally:
        stream_handler.setStream(prev_stream)

    assert result == "Free cash flow measures cash."
    assert route.called
    sent_request = route.calls[0].request
    assert sent_request.headers["Authorization"] == "Bearer sk-or-test-key-123"
    assert sent_request.headers["HTTP-Referer"] == "https://aacharya.app"
    assert sent_request.headers["X-Title"] == "Aacharya"

    body = json.loads(sent_request.content.decode("utf-8"))
    assert body["messages"] == [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Explain free cash flow briefly."},
    ]
    assert "response_format" not in body

    summary = get_usage_summary()
    assert summary["total_calls"] == 1
    assert summary["prompt_tokens"] == 120
    assert summary["completion_tokens"] == 30
    assert summary["total_tokens"] == 150
    assert summary["total_cost_usd"] == pytest.approx(0.00024)

    log_payload = json.loads(log_buffer.getvalue().strip().splitlines()[-1])
    assert log_payload["message"] == "llm_call_completed"
    assert log_payload["extra"]["prompt_tokens"] == 120
    assert log_payload["extra"]["completion_tokens"] == 30
    assert log_payload["extra"]["cost_usd"] == pytest.approx(0.00024)


@respx.mock
def test_complete_pydantic_schema_strips_markdown_fences() -> None:
    fenced_json = (
        '```json\n{"symbol": "RELIANCE", "direction": "up", "confidence": 0.82}\n```'
    )
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": fenced_json}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
            },
        )
    )

    parsed = complete("Extract claim", schema=ClaimExtraction)

    assert isinstance(parsed, ClaimExtraction)
    assert parsed.symbol == "RELIANCE"
    assert parsed.direction == "up"
    assert parsed.confidence == pytest.approx(0.82)

    req_body = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert req_body["response_format"]["type"] == "json_schema"
    assert req_body["response_format"]["json_schema"]["name"] == "ClaimExtraction"
    assert req_body["response_format"]["json_schema"]["strict"] is True

    # Fallback cost calculation when OpenRouter omits `usage.cost`
    summary = get_usage_summary()
    expected_cost = (1000 * 0.10 + 500 * 0.40) / 1_000_000.0
    assert summary["total_cost_usd"] == pytest.approx(expected_cost)


@respx.mock
def test_complete_dict_schema() -> None:
    raw_schema = {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
        "additionalProperties": False,
    }
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"summary": "Neutral"}',
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 40,
                    "completion_tokens": 10,
                    "cost": 0.00001,
                },
            },
        )
    )

    parsed = complete("Summarize", schema=raw_schema)

    assert parsed == {"summary": "Neutral"}
    req_body = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert req_body["response_format"]["json_schema"]["name"] == "structured_output"
    assert req_body["response_format"]["json_schema"]["schema"] == raw_schema


@respx.mock
def test_complete_retries_on_429_and_500_then_succeeds() -> None:
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(429, json={"error": "rate_limited"}),
            httpx.Response(500, json={"error": "upstream_error"}),
            httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "Recovered"}}
                    ],
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 5,
                        "cost": 0.00001,
                    },
                },
            ),
        ]
    )

    result = complete("Test retry")

    assert result == "Recovered"
    assert route.call_count == 3


@respx.mock
def test_complete_raises_external_service_error_after_exhausted_retries() -> None:
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(503, json={"error": "unavailable"})
    )

    with pytest.raises(ExternalServiceError):
        complete("Test exhausted retry")

    assert route.call_count == 3


@respx.mock
def test_complete_non_retryable_4xx_fails_immediately() -> None:
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": "invalid api key"})
    )

    with pytest.raises(ExternalServiceError):
        complete("Test 401")

    assert route.call_count == 1


def test_complete_raises_configuration_error_when_api_key_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(ConfigurationError):
        complete("Hello")


@pytest.mark.asyncio
@respx.mock
async def test_acomplete_structured_output() -> None:
    payload_json = '{"symbol": "INFY", "direction": "down", "confidence": 0.65}'
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": payload_json}}
                ],
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 20,
                    "cost": 0.00002,
                },
            },
        )
    )

    parsed = await acomplete("Async claim", schema=ClaimExtraction)
    assert isinstance(parsed, ClaimExtraction)
    assert parsed.symbol == "INFY"
    assert parsed.direction == "down"


@respx.mock
def test_complete_free_nemotron_models_log_zero_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Free OpenRouter Nemotron models resolve to $0.0 fallback cost."""
    for model_name in (
        "nvidia/nemotron-3.5-lightning:free",
        "nvidia/nemotron-3.5-super-vl:free",
    ):
        reset_usage_summary()
        monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", model_name)
        get_settings.cache_clear()
        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "Zero cost ok"}}
                    ],
                    "usage": {"prompt_tokens": 2000, "completion_tokens": 500},
                },
            )
        )

        result = complete("Hello Nemotron")
        assert result == "Zero cost ok"
        summary = get_usage_summary()
        assert summary["total_cost_usd"] == 0.0
        assert summary["by_model"][model_name]["cost_usd"] == 0.0
