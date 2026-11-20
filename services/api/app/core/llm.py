"""Shared OpenRouter LLM client with structured outputs, retries, and cost tracking."""

from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, TypeVar, cast, overload

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.errors import ConfigurationError, ExternalServiceError
from app.core.logging import get_logger

T = TypeVar("T", bound=BaseModel)

_logger = get_logger("core.llm")

_FENCE_RE = re.compile(r"^```(?:json|JSON)?\s*(.*?)\s*```$", re.DOTALL)

# Fallback USD pricing per 1M tokens: (input_per_1m, output_per_1m).
MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "anthropic/claude-3.5-sonnet": (3.00, 15.00),
    "anthropic/claude-3-5-haiku": (0.80, 4.00),
    "meta-llama/llama-3.1-70b-instruct": (0.52, 0.75),
}
_DEFAULT_PRICING_PER_1M: tuple[float, float] = (0.15, 0.60)

_usage_lock = threading.Lock()
_usage_state: dict[str, Any] = {
    "total_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "total_cost_usd": 0.0,
    "by_model": {},
}


class _RetryableLLMError(Exception):
    """Internal marker for transient OpenRouter errors eligible for retry."""


def get_usage_summary() -> dict[str, Any]:
    """Return a thread-safe snapshot of accumulated LLM token and cost metrics."""
    with _usage_lock:
        by_model_copy = {
            model_name: dict(stats)
            for model_name, stats in _usage_state["by_model"].items()
        }
        return {
            "total_calls": int(_usage_state["total_calls"]),
            "prompt_tokens": int(_usage_state["prompt_tokens"]),
            "completion_tokens": int(_usage_state["completion_tokens"]),
            "total_tokens": int(_usage_state["total_tokens"]),
            "total_cost_usd": round(float(_usage_state["total_cost_usd"]), 8),
            "by_model": by_model_copy,
        }


def reset_usage_summary() -> None:
    """Reset accumulated LLM usage counters (intended for test isolation)."""
    with _usage_lock:
        _usage_state["total_calls"] = 0
        _usage_state["prompt_tokens"] = 0
        _usage_state["completion_tokens"] = 0
        _usage_state["total_tokens"] = 0
        _usage_state["total_cost_usd"] = 0.0
        _usage_state["by_model"] = {}


def _strip_json_fences(raw: str) -> str:
    """Strip optional Markdown ```json ... ``` code fences from an LLM response."""
    stripped = raw.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _resolve_config(model: str | None) -> tuple[str, str, str]:
    """Validate API key and resolve endpoint URL and model name."""
    settings = get_settings()
    api_key = settings.openrouter_api_key.strip()
    if not api_key:
        raise ConfigurationError("OPENROUTER_API_KEY is not configured")

    base_url = settings.openrouter_base_url.rstrip("/")
    resolved_model = (model or settings.openrouter_default_model).strip()
    if not resolved_model:
        raise ConfigurationError("OPENROUTER_DEFAULT_MODEL is not configured")

    return api_key, f"{base_url}/chat/completions", resolved_model


def _build_headers(api_key: str) -> dict[str, str]:
    """Build standard OpenRouter request headers."""
    return {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://aacharya.app",
        "X-Title": "Aacharya",
        "Content-Type": "application/json",
    }


def _build_payload(
    prompt: str,
    schema: type[T] | dict[str, Any] | None,
    *,
    system: str | None,
    model: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Construct an OpenRouter chat completions payload."""
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if schema is not None:
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            }
        elif isinstance(schema, dict):
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "strict": True,
                    "schema": schema,
                },
            }
        else:
            raise ValueError(
                "schema must be a Pydantic BaseModel subclass, dict, or None"
            )

    return payload


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost using fallback per-million-token pricing."""
    in_rate, out_rate = MODEL_PRICING_PER_1M.get(model, _DEFAULT_PRICING_PER_1M)
    return (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000.0


def _record_usage(
    model: str,
    usage_data: dict[str, Any],
    *,
    latency_ms: float,
    structured: bool,
) -> None:
    """Extract tokens/cost, emit structured JSON log, and update thread-safe totals."""
    prompt_tokens = int(usage_data.get("prompt_tokens") or 0)
    completion_tokens = int(usage_data.get("completion_tokens") or 0)
    total_tokens = int(
        usage_data.get("total_tokens") or (prompt_tokens + completion_tokens)
    )

    raw_cost = usage_data.get("cost")
    if raw_cost is not None:
        cost_usd = float(raw_cost)
    else:
        cost_usd = _estimate_cost(model, prompt_tokens, completion_tokens)

    with _usage_lock:
        _usage_state["total_calls"] += 1
        _usage_state["prompt_tokens"] += prompt_tokens
        _usage_state["completion_tokens"] += completion_tokens
        _usage_state["total_tokens"] += total_tokens
        _usage_state["total_cost_usd"] += cost_usd

        by_model = _usage_state["by_model"]
        model_stats = by_model.setdefault(
            model,
            {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
            },
        )
        model_stats["calls"] += 1
        model_stats["prompt_tokens"] += prompt_tokens
        model_stats["completion_tokens"] += completion_tokens
        model_stats["total_tokens"] += total_tokens
        model_stats["cost_usd"] = round(float(model_stats["cost_usd"]) + cost_usd, 8)

    _logger.info(
        "llm_call_completed",
        extra={
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost_usd, 8),
            "latency_ms": round(latency_ms, 2),
            "structured": structured,
        },
    )


def _extract_content(response: httpx.Response) -> tuple[str, dict[str, Any]]:
    """Validate HTTP status and extract assistant text content plus usage metadata."""
    status = response.status_code
    if status == 429 or status >= 500:
        raise _RetryableLLMError(
            f"OpenRouter transient HTTP {status}: {response.text[:200]}"
        )

    if 400 <= status < 500:
        raise ExternalServiceError(
            f"OpenRouter request rejected with HTTP {status}: {response.text[:300]}"
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise _RetryableLLMError("OpenRouter returned invalid JSON payload") from exc

    if not isinstance(body, dict):
        raise _RetryableLLMError("OpenRouter response JSON root is not an object")

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise _RetryableLLMError("OpenRouter response missing choices")

    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise _RetryableLLMError("OpenRouter response missing assistant content string")

    raw_usage = body.get("usage")
    usage = raw_usage if isinstance(raw_usage, dict) else {}
    return content, usage


def _parse_structured_output(
    content: str,
    schema: type[T] | dict[str, Any] | None,
) -> str | T | dict[str, Any]:
    """Parse raw text or validate structured JSON output against a Pydantic/dict schema."""
    if schema is None:
        return content

    cleaned = _strip_json_fences(content)
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        try:
            return schema.model_validate_json(cleaned)
        except ValidationError as exc:
            raise _RetryableLLMError(
                f"Structured output failed {schema.__name__} validation"
            ) from exc

    if isinstance(schema, dict):
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise _RetryableLLMError("Structured output was not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise _RetryableLLMError("Structured JSON output must be a JSON object")
        return cast(dict[str, Any], parsed)

    raise ValueError("schema must be a Pydantic BaseModel subclass, dict, or None")


def _retry_policy() -> dict[str, Any]:
    """Common tenacity retry configuration (3 attempts, exponential backoff)."""
    return {
        "stop": stop_after_attempt(3),
        "wait": wait_exponential(multiplier=0.2, min=0.1, max=2.0),
        "retry": retry_if_exception_type(
            (_RetryableLLMError, httpx.TimeoutException, httpx.TransportError)
        ),
        "reraise": True,
    }


@overload
def complete(
    prompt: str,
    schema: None = None,
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout_s: float = 30.0,
) -> str: ...


@overload
def complete(
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout_s: float = 30.0,
) -> T: ...


@overload
def complete(
    prompt: str,
    schema: dict[str, Any],
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout_s: float = 30.0,
) -> dict[str, Any]: ...


def complete(
    prompt: str,
    schema: type[T] | dict[str, Any] | None = None,
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout_s: float = 30.0,
) -> str | T | dict[str, Any]:
    """Call OpenRouter synchronously with optional JSON schema validation and retries."""
    api_key, endpoint, resolved_model = _resolve_config(model)
    headers = _build_headers(api_key)
    payload = _build_payload(
        prompt,
        schema,
        system=system,
        model=resolved_model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_s) as client:
            for attempt in Retrying(**_retry_policy()):
                with attempt:
                    response = client.post(endpoint, headers=headers, json=payload)
                    content, usage = _extract_content(response)
                    parsed = _parse_structured_output(content, schema)
                    latency_ms = (time.perf_counter() - started) * 1000.0
                    _record_usage(
                        resolved_model,
                        usage,
                        latency_ms=latency_ms,
                        structured=schema is not None,
                    )
                    return parsed
    except (_RetryableLLMError, httpx.TimeoutException, httpx.TransportError) as exc:
        raise ExternalServiceError(
            f"OpenRouter call failed after retries: {exc}"
        ) from exc

    raise ExternalServiceError("OpenRouter call failed unexpectedly")


@overload
async def acomplete(
    prompt: str,
    schema: None = None,
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout_s: float = 30.0,
) -> str: ...


@overload
async def acomplete(
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout_s: float = 30.0,
) -> T: ...


@overload
async def acomplete(
    prompt: str,
    schema: dict[str, Any],
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout_s: float = 30.0,
) -> dict[str, Any]: ...


async def acomplete(
    prompt: str,
    schema: type[T] | dict[str, Any] | None = None,
    *,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout_s: float = 30.0,
) -> str | T | dict[str, Any]:
    """Call OpenRouter asynchronously with optional JSON schema validation and retries."""
    api_key, endpoint, resolved_model = _resolve_config(model)
    headers = _build_headers(api_key)
    payload = _build_payload(
        prompt,
        schema,
        system=system,
        model=resolved_model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async for attempt in AsyncRetrying(**_retry_policy()):
                with attempt:
                    response = await client.post(
                        endpoint, headers=headers, json=payload
                    )
                    content, usage = _extract_content(response)
                    parsed = _parse_structured_output(content, schema)
                    latency_ms = (time.perf_counter() - started) * 1000.0
                    _record_usage(
                        resolved_model,
                        usage,
                        latency_ms=latency_ms,
                        structured=schema is not None,
                    )
                    return parsed
    except (_RetryableLLMError, httpx.TimeoutException, httpx.TransportError) as exc:
        raise ExternalServiceError(
            f"OpenRouter async call failed after retries: {exc}"
        ) from exc

    raise ExternalServiceError("OpenRouter async call failed unexpectedly")
