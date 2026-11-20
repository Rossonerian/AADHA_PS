"""End-to-end staging and platform smoke test script for PaisaProof API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def _acquire_jwt(
    *,
    jwt_token: str | None,
    supabase_url: str | None,
    supabase_anon_key: str | None,
    email: str | None,
    password: str | None,
    timeout: float,
) -> str:
    if jwt_token and jwt_token.strip():
        return jwt_token.strip()

    if supabase_url and supabase_anon_key and email and password:
        auth_url = f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
        resp = httpx.post(
            auth_url,
            headers={
                "apikey": supabase_anon_key,
                "Content-Type": "application/json",
            },
            json={"email": email, "password": password},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get("access_token")
        if isinstance(access_token, str) and access_token.strip():
            return access_token.strip()
        raise RuntimeError("Supabase auth response missing access_token")

    raise RuntimeError(
        "No JWT provided. Supply --jwt / SMOKE_TEST_JWT or "
        "SUPABASE_URL + SUPABASE_ANON_KEY + SMOKE_TEST_EMAIL + SMOKE_TEST_PASSWORD."
    )


def _assert_ok(resp: httpx.Response, label: str) -> dict[str, Any]:
    if resp.status_code != 200:
        raise RuntimeError(f"{label} failed with HTTP {resp.status_code}: {resp.text}")
    data = resp.json()
    if not isinstance(data, dict):
        raise TypeError(f"{label} returned non-object JSON: {data!r}")
    return data


def run_smoke_test(
    *,
    base_url: str,
    jwt_token: str | None = None,
    supabase_url: str | None = None,
    supabase_anon_key: str | None = None,
    email: str | None = None,
    password: str | None = None,
    platform_only: bool = False,
    timeout: float = 15.0,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Execute platform-only or full C2-C4 smoke checks and return structured summary."""
    normalized_base = base_url.rstrip("/")
    owns_client = http_client is None
    client = http_client or httpx.Client(base_url=normalized_base, timeout=timeout)
    checks: list[dict[str, Any]] = []

    try:
        # 1. /health
        health_data = _assert_ok(client.get("/health"), "GET /health")
        if health_data.get("db") != "ok":
            raise RuntimeError(f"/health db check failed: {health_data!r}")
        if not health_data.get("market_data_as_of"):
            raise RuntimeError(
                f"/health market_data_as_of is missing/null: {health_data!r}"
            )
        checks.append({"step": "health", "status": "ok", "data": health_data})

        # 2. /me unauthenticated must be 401
        unauth_resp = client.get("/me")
        if unauth_resp.status_code != 401:
            raise RuntimeError(
                f"Expected 401 for unauthenticated GET /me, got {unauth_resp.status_code}"
            )
        checks.append({"step": "me_unauthenticated_401", "status": "ok"})

        # 3. Acquire JWT and verify authenticated /me
        token = _acquire_jwt(
            jwt_token=jwt_token,
            supabase_url=supabase_url,
            supabase_anon_key=supabase_anon_key,
            email=email,
            password=password,
            timeout=timeout,
        )
        auth_headers = {"Authorization": f"Bearer {token}"}
        me_data = _assert_ok(client.get("/me", headers=auth_headers), "GET /me")
        for key in ("id", "level", "unlocks"):
            if key not in me_data:
                raise RuntimeError(f"GET /me missing key '{key}': {me_data!r}")
        checks.append(
            {"step": "me_authenticated", "status": "ok", "level": me_data["level"]}
        )

        if platform_only:
            return {
                "status": "ok",
                "mode": "platform-only",
                "base_url": normalized_base,
                "checks": checks,
            }

        # 4. Onboarding flow
        onb_start = _assert_ok(
            client.post("/onboarding/start", headers=auth_headers),
            "POST /onboarding/start",
        )
        session_id = onb_start["session_id"]
        question = onb_start.get("question")
        while question is not None:
            options = question.get("options") or ["A"]
            ans_resp = _assert_ok(
                client.post(
                    "/onboarding/answer",
                    headers=auth_headers,
                    json={
                        "session_id": session_id,
                        "question_id": question["id"],
                        "answer": options[0],
                        "confidence": 70,
                    },
                ),
                "POST /onboarding/answer",
            )
            question = ans_resp.get("next_question")
        checks.append({"step": "onboarding", "status": "ok"})

        # 5. Learning plan + lesson
        plan_data = _assert_ok(client.get("/plan", headers=auth_headers), "GET /plan")
        lessons = plan_data.get("lessons") or []
        if not lessons:
            raise RuntimeError(f"GET /plan returned no lessons: {plan_data!r}")
        first_lesson_id = lessons[0]["id"]
        _assert_ok(
            client.get(f"/lessons/{first_lesson_id}", headers=auth_headers),
            f"GET /lessons/{first_lesson_id}",
        )
        checks.append({"step": "plan_and_lesson", "status": "ok"})

        # 6. Scenario practice
        scenario = _assert_ok(
            client.get("/scenarios/next", headers=auth_headers),
            "GET /scenarios/next",
        )
        _assert_ok(
            client.post(
                f"/scenarios/{scenario['id']}/answer",
                headers=auth_headers,
                json={"direction": "up", "confidence": 65, "clues": []},
            ),
            "POST /scenarios/{id}/answer",
        )
        checks.append({"step": "scenarios", "status": "ok"})

        # 7. Assessment + unlock check
        level = int(me_data.get("level") or 1)
        assess_start = _assert_ok(
            client.post(f"/assessments/{level}/start", headers=auth_headers),
            f"POST /assessments/{level}/start",
        )
        answers = [
            {
                "item_id": item["id"],
                "answer": (item.get("options") or ["A"])[0],
                "confidence": 75,
            }
            for item in assess_start.get("items", [])
        ]
        _assert_ok(
            client.post(
                f"/assessments/{assess_start['assessment_id']}/submit",
                headers=auth_headers,
                json={"answers": answers},
            ),
            "POST /assessments/{id}/submit",
        )
        me_after = _assert_ok(client.get("/me", headers=auth_headers), "GET /me (post)")
        checks.append(
            {
                "step": "assessment_and_unlocks",
                "status": "ok",
                "unlocks": me_after["unlocks"],
            }
        )

        # 8. Verifier
        _assert_ok(
            client.post(
                "/verify",
                headers=auth_headers,
                json={
                    "text": "Guaranteed 30% return in SUZLON within 10 days! Buy now!"
                },
            ),
            "POST /verify",
        )
        checks.append({"step": "verify", "status": "ok"})

        # 9. Dashboard
        _assert_ok(
            client.get("/me/dashboard", headers=auth_headers),
            "GET /me/dashboard",
        )
        checks.append({"step": "dashboard", "status": "ok"})

        return {
            "status": "ok",
            "mode": "full",
            "base_url": normalized_base,
            "checks": checks,
        }
    finally:
        if owns_client:
            client.close()


def main() -> int:
    """CLI entrypoint for `infra/scripts/smoke_test.py`."""
    parser = argparse.ArgumentParser(description="Run PaisaProof API smoke tests.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("STAGING_API_URL", "http://localhost:8000/api/v1"),
        help="API base URL including /api/v1.",
    )
    parser.add_argument(
        "--jwt",
        default=os.getenv("SMOKE_TEST_JWT"),
        help="Optional pre-minted Supabase Bearer JWT.",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("SMOKE_TEST_EMAIL"),
        help="Supabase smoke test user email.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("SMOKE_TEST_PASSWORD"),
        help="Supabase smoke test user password.",
    )
    parser.add_argument(
        "--platform-only",
        action="store_true",
        help="Verify only platform /health and /me (C1 gate).",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    try:
        result = run_smoke_test(
            base_url=args.base_url,
            jwt_token=args.jwt,
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY"),
            email=args.email,
            password=args.password,
            platform_only=args.platform_only,
            timeout=args.timeout,
        )
    except (
        httpx.HTTPError,
        RuntimeError,
        ValueError,
        TypeError,
        KeyError,
        OSError,
    ) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
