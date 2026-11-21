"""End-to-end staging and platform smoke test script for PaisaProof API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import date as DateType
from pathlib import Path
from typing import Any

import httpx
import psycopg
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

_BARE_ORIGIN_RE = re.compile(r"^https?://[^/]+$", re.IGNORECASE)


def _normalize_api_base(base_url: str) -> str:
    trimmed = base_url.strip().rstrip("/")
    if _BARE_ORIGIN_RE.match(trimmed):
        return f"{trimmed}/api/v1"
    return trimmed


def _check_market_freshness(as_of_raw: Any, max_stale_days: int) -> None:
    if not isinstance(as_of_raw, str) or not as_of_raw.strip():
        raise RuntimeError(f"/health market_data_as_of is missing/null: {as_of_raw!r}")
    if max_stale_days <= 0:
        return
    try:
        as_of_date = DateType.fromisoformat(as_of_raw.strip()[:10])
    except ValueError as exc:
        raise RuntimeError(
            f"/health market_data_as_of has invalid date: {as_of_raw!r}"
        ) from exc
    age_days = (DateType.today() - as_of_date).days
    if age_days > max_stale_days:
        raise RuntimeError(
            f"/health market_data_as_of={as_of_raw} is stale "
            f"({age_days}d > max {max_stale_days}d)"
        )


def _load_question_answers() -> dict[str, str]:
    questions_path = REPO_ROOT / "data" / "seed" / "education" / "questions.yaml"
    if not questions_path.exists():
        return {}
    payload = yaml.safe_load(questions_path.read_text(encoding="utf-8")) or {}
    answers: dict[str, str] = {}
    for item in payload.get("questions", []):
        if isinstance(item, dict) and item.get("id") and item.get("answer"):
            answers[str(item["id"])] = str(item["answer"])
    return answers


def _create_fresh_neon_user(
    *,
    neon_auth_base_url: str,
    origin: str,
    timeout: float,
) -> tuple[str, str | None]:
    auth_base = neon_auth_base_url.strip().rstrip("/")
    request_origin = origin.strip().rstrip("/") or "http://localhost:3000"
    tag = uuid.uuid4().hex[:8]
    email = f"smoke-{tag}@paisaproof.test"
    password = f"Smoke!{uuid.uuid4().hex[:10]}Aa"

    with httpx.Client(timeout=timeout, follow_redirects=True) as auth_client:
        signup_resp = auth_client.post(
            f"{auth_base}/sign-up/email",
            headers={
                "Origin": request_origin,
                "Content-Type": "application/json",
            },
            json={
                "email": email,
                "password": password,
                "name": f"Smoke {tag}",
            },
        )
        if signup_resp.status_code != 200:
            raise RuntimeError(
                f"Fresh Neon Auth sign-up failed ({signup_resp.status_code}): "
                f"{signup_resp.text[:300]}"
            )
        signup_data = signup_resp.json()
        raw_uid = (signup_data.get("user") or {}).get("id")
        user_id = str(raw_uid) if raw_uid else None

        session_resp = auth_client.get(
            f"{auth_base}/get-session",
            headers={"Origin": request_origin},
        )
        session_resp.raise_for_status()
        sess_uid = ((session_resp.json() or {}).get("user") or {}).get("id")
        if user_id and sess_uid != user_id:
            raise RuntimeError(
                f"Neon Auth session mismatch after sign-up: {sess_uid!r} vs {user_id!r}"
            )

        token_resp = auth_client.get(
            f"{auth_base}/token",
            headers={"Origin": request_origin},
        )
        token_resp.raise_for_status()
        token = token_resp.json().get("token")
        if isinstance(token, str) and len(token.split(".")) == 3:
            return token.strip(), user_id

    raise RuntimeError("Neon Auth /token response missing valid JWT for fresh user")


def _cleanup_test_user(db_url: str, user_id: str) -> dict[str, int]:
    raw_pg_url = db_url.strip().replace("postgresql+psycopg://", "postgresql://")
    deleted: dict[str, int] = {}
    with psycopg.connect(raw_pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.claims WHERE submission_id IN "
                "(SELECT id FROM public.submissions WHERE user_id = %s)",
                (user_id,),
            )
            deleted["claims"] = cur.rowcount

            for table in (
                "submissions",
                "attempts",
                "edu_sessions",
                "plans",
                "skill_scores",
                "unlocks",
            ):
                cur.execute(
                    f"DELETE FROM public.{table} WHERE user_id = %s", (user_id,)
                )
                deleted[table] = cur.rowcount

            cur.execute("DELETE FROM public.users WHERE id = %s", (user_id,))
            deleted["users"] = cur.rowcount

            cur.execute('DELETE FROM neon_auth.session WHERE "userId" = %s', (user_id,))
            deleted["neon_sessions"] = cur.rowcount
            cur.execute('DELETE FROM neon_auth.account WHERE "userId" = %s', (user_id,))
            deleted["neon_accounts"] = cur.rowcount
            cur.execute('DELETE FROM neon_auth."user" WHERE id = %s', (user_id,))
            deleted["neon_users"] = cur.rowcount
        conn.commit()
    return deleted


def _acquire_jwt(
    *,
    jwt_token: str | None,
    fresh_user: bool = False,
    neon_auth_base_url: str | None = None,
    origin: str | None = None,
    supabase_url: str | None = None,
    supabase_anon_key: str | None = None,
    email: str | None = None,
    password: str | None = None,
    timeout: float = 15.0,
) -> tuple[str, str | None]:
    if jwt_token and jwt_token.strip():
        return jwt_token.strip(), None

    if fresh_user:
        if not neon_auth_base_url or not neon_auth_base_url.strip():
            raise RuntimeError(
                "--fresh-user requires --auth-base-url or NEON_AUTH_BASE_URL."
            )
        token, user_id = _create_fresh_neon_user(
            neon_auth_base_url=neon_auth_base_url,
            origin=origin or "http://localhost:3000",
            timeout=timeout,
        )
        return token, user_id

    if neon_auth_base_url and email and password:
        auth_base = neon_auth_base_url.strip().rstrip("/")
        request_origin = (origin or "http://localhost:3000").strip().rstrip("/")
        with httpx.Client(timeout=timeout, follow_redirects=True) as auth_client:
            signin_resp = auth_client.post(
                f"{auth_base}/sign-in/email",
                headers={
                    "Origin": request_origin,
                    "Content-Type": "application/json",
                },
                json={"email": email, "password": password},
            )
            signin_resp.raise_for_status()
            token_resp = auth_client.get(
                f"{auth_base}/token",
                headers={"Origin": request_origin},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            token = token_data.get("token")
            if isinstance(token, str) and token.strip():
                return token.strip(), None
        raise RuntimeError("Neon Auth /token response missing token")

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
            return access_token.strip(), None
        raise RuntimeError("Supabase auth response missing access_token")

    raise RuntimeError(
        "No JWT provided. Supply --jwt / SMOKE_TEST_JWT, --fresh-user, or "
        "NEON_AUTH_BASE_URL + SMOKE_TEST_EMAIL + SMOKE_TEST_PASSWORD."
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
    fresh_user: bool = False,
    neon_auth_base_url: str | None = None,
    origin: str | None = None,
    supabase_url: str | None = None,
    supabase_anon_key: str | None = None,
    email: str | None = None,
    password: str | None = None,
    health_only: bool = False,
    platform_only: bool = False,
    max_stale_days: int = 5,
    cleanup_db: bool = False,
    db_url: str | None = None,
    timeout: float = 15.0,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Execute health-only, platform-only, or full C2-C4 API smoke checks."""
    normalized_base = _normalize_api_base(base_url)
    owns_client = http_client is None
    client = http_client or httpx.Client(base_url=normalized_base, timeout=timeout)
    checks: list[dict[str, Any]] = []
    created_user_id: str | None = None
    cleanup_summary: dict[str, int] | None = None
    current_step = "health"

    try:
        # 1. /health (+ stale market data freshness check)
        health_data = _assert_ok(client.get("/health"), "GET /health")
        if health_data.get("status") != "ok" or health_data.get("db") != "ok":
            raise RuntimeError(f"/health check failed: {health_data!r}")
        _check_market_freshness(health_data.get("market_data_as_of"), max_stale_days)
        checks.append({"step": "health", "status": "ok", "data": health_data})

        # 2. /me unauthenticated must be 401
        current_step = "me_unauthenticated_401"
        unauth_resp = client.get("/me")
        if unauth_resp.status_code != 401:
            raise RuntimeError(
                f"Expected 401 for unauthenticated GET /me, got {unauth_resp.status_code}"
            )
        checks.append({"step": "me_unauthenticated_401", "status": "ok"})

        if health_only:
            return {
                "status": "ok",
                "mode": "health-only",
                "base_url": normalized_base,
                "checks": checks,
            }

        # 3. Acquire JWT and verify authenticated /me
        current_step = "acquire_jwt"
        token, created_user_id = _acquire_jwt(
            jwt_token=jwt_token,
            fresh_user=fresh_user,
            neon_auth_base_url=neon_auth_base_url,
            origin=origin,
            supabase_url=supabase_url,
            supabase_anon_key=supabase_anon_key,
            email=email,
            password=password,
            timeout=timeout,
        )
        auth_headers = {"Authorization": f"Bearer {token}"}
        current_step = "me_authenticated"
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

        # 4. Onboarding flow (onboarding -> placement level + Brier; conf=55 targets L3 for assessment)
        current_step = "onboarding"
        answer_key = _load_question_answers()
        onb_start = _assert_ok(
            client.post("/onboarding/start", headers=auth_headers),
            "POST /onboarding/start",
        )
        session_id = onb_start["session_id"]
        question = onb_start.get("question")
        onb_result: dict[str, Any] | None = None
        answered_count = 0
        while question is not None:
            options = question.get("options") or ["A"]
            qid = str(question["id"])
            chosen_answer = answer_key.get(qid, options[0])
            confidence = 55 if qid in answer_key else 70
            ans_resp = _assert_ok(
                client.post(
                    "/onboarding/answer",
                    headers=auth_headers,
                    json={
                        "session_id": session_id,
                        "question_id": qid,
                        "answer": chosen_answer,
                        "confidence": confidence,
                    },
                ),
                "POST /onboarding/answer",
            )
            answered_count += 1
            if isinstance(ans_resp.get("result"), dict):
                onb_result = ans_resp["result"]
            question = ans_resp.get("next_question")
        if not onb_result or "level" not in onb_result:
            raise RuntimeError("Onboarding completed without placement result")
        placed_level = int(onb_result["level"])
        current_level = placed_level
        checks.append(
            {
                "step": "onboarding",
                "status": "ok",
                "questions_answered": answered_count,
                "level": placed_level,
                "brier": onb_result.get("brier"),
            }
        )

        # 5. Learning plan + lesson
        current_step = "plan_and_lesson"
        plan_data = _assert_ok(client.get("/plan", headers=auth_headers), "GET /plan")
        lessons = plan_data.get("lessons") or []
        if not lessons:
            raise RuntimeError(f"GET /plan returned no lessons: {plan_data!r}")
        first_lesson_id = lessons[0]["id"]
        lesson_data = _assert_ok(
            client.get(f"/lessons/{first_lesson_id}", headers=auth_headers),
            f"GET /lessons/{first_lesson_id}",
        )
        checks.append(
            {
                "step": "plan_and_lesson",
                "status": "ok",
                "lesson_id": first_lesson_id,
                "data_origin": lesson_data.get("data_origin"),
            }
        )

        # 6. Level-up assessment (L3 -> L4 unlock so dashboard & explain unlock cleanly)
        current_step = "assessment"
        target_level = current_level if 1 <= current_level <= 3 else 3
        asmt_start = _assert_ok(
            client.post(f"/assessments/{target_level}/start", headers=auth_headers),
            f"POST /assessments/{target_level}/start",
        )
        assessment_id = str(asmt_start.get("assessment_id") or "")
        asmt_items = asmt_start.get("items") or []
        if not assessment_id or not asmt_items:
            raise RuntimeError(
                f"POST /assessments/{target_level}/start returned invalid payload: {asmt_start!r}"
            )
        asmt_answers: list[dict[str, Any]] = []
        for item in asmt_items:
            item_id = str(item["item_id"])
            item_type = str(item.get("item_type", "question"))
            if item_type == "scenario":
                asmt_answers.append(
                    {"item_id": item_id, "answer": "down", "confidence": 50}
                )
            else:
                prompt_obj = item.get("prompt") or {}
                options = prompt_obj.get("options") or ["A"]
                chosen = answer_key.get(item_id, options[0])
                conf = 90 if item_id in answer_key else 70
                asmt_answers.append(
                    {"item_id": item_id, "answer": chosen, "confidence": conf}
                )
        asmt_submit = _assert_ok(
            client.post(
                f"/assessments/{assessment_id}/submit",
                headers=auth_headers,
                json={"answers": asmt_answers},
            ),
            f"POST /assessments/{assessment_id}/submit",
        )
        if answer_key and not asmt_submit.get("passed"):
            raise RuntimeError(f"Assessment did not pass: {asmt_submit!r}")
        if isinstance(asmt_submit.get("new_level"), int):
            current_level = int(asmt_submit["new_level"])
        checks.append(
            {
                "step": "assessment",
                "status": "ok",
                "assessment_id": assessment_id,
                "target_level": target_level,
                "passed": asmt_submit.get("passed"),
                "score": asmt_submit.get("score"),
                "brier": asmt_submit.get("brier"),
                "new_level": current_level,
            }
        )

        # 7. Scenario practice
        current_step = "scenarios"
        scenario = _assert_ok(
            client.get("/scenarios/next", headers=auth_headers),
            "GET /scenarios/next",
        )
        scenario_answer = _assert_ok(
            client.post(
                f"/scenarios/{scenario['id']}/answer",
                headers=auth_headers,
                json={"direction": "down", "confidence": 70, "clues": []},
            ),
            "POST /scenarios/{id}/answer",
        )
        if "outcome" not in scenario_answer or "explanation" not in scenario_answer:
            raise RuntimeError(
                f"Scenario answer missing outcome/explanation: {scenario_answer!r}"
            )
        checks.append(
            {
                "step": "scenarios",
                "status": "ok",
                "scenario_id": scenario["id"],
                "data_origin": scenario_answer.get("data_origin"),
            }
        )

        # 8. Explain a stock (Level >= 2 unlocked, else expect 403 TOOL_LOCKED)
        current_step = "explain"
        explain_resp = client.get(
            "/explain",
            params={"symbol": "TCS", "year": 2020},
            headers=auth_headers,
        )
        if current_level >= 2:
            explain_data = _assert_ok(explain_resp, "GET /explain?symbol=TCS&year=2020")
            for req_key in ("chart", "moves", "summary", "data_origin"):
                if req_key not in explain_data:
                    raise RuntimeError(
                        f"GET /explain missing '{req_key}': {explain_data!r}"
                    )
            checks.append(
                {
                    "step": "explain",
                    "status": "ok",
                    "symbol": explain_data.get("symbol"),
                    "data_origin": explain_data.get("data_origin"),
                }
            )
        else:
            if explain_resp.status_code != 403:
                raise RuntimeError(
                    f"Expected 403 TOOL_LOCKED on GET /explain at level {current_level}, "
                    f"got {explain_resp.status_code}"
                )
            checks.append({"step": "explain", "status": "ok_locked_403"})

        # 9. Verifier (POST /verify + GET /submissions/mine)
        current_step = "verify"
        verify_data = _assert_ok(
            client.post(
                "/verify",
                headers=auth_headers,
                json={
                    "text": "RELIANCE buy karo target 1600 SL 1200 guaranteed 20% return"
                },
            ),
            "POST /verify",
        )
        mine_data = _assert_ok(
            client.get("/submissions/mine", headers=auth_headers),
            "GET /submissions/mine",
        )
        if len(mine_data.get("items") or []) < 1:
            raise RuntimeError(
                f"GET /submissions/mine returned no items after verify: {mine_data!r}"
            )
        checks.append(
            {
                "step": "verify",
                "status": "ok",
                "mode": verify_data.get("mode"),
                "submissions_count": len(mine_data.get("items") or []),
                "data_origin": (verify_data.get("source") or {}).get("data_origin"),
            }
        )

        # 10. Dashboard (Level >= 4 unlocked, else expect 403 TOOL_LOCKED)
        current_step = "dashboard"
        dashboard_resp = client.get("/me/dashboard", headers=auth_headers)
        if current_level >= 4:
            dash_data = _assert_ok(dashboard_resp, "GET /me/dashboard")
            for req_key in (
                "level",
                "skills_over_time",
                "brier_over_time",
                "scenario_accuracy",
            ):
                if req_key not in dash_data:
                    raise RuntimeError(
                        f"GET /me/dashboard missing '{req_key}': {dash_data!r}"
                    )
            checks.append(
                {
                    "step": "dashboard",
                    "status": "ok",
                    "level": dash_data.get("level"),
                }
            )
        else:
            if dashboard_resp.status_code != 403:
                raise RuntimeError(
                    f"Expected 403 TOOL_LOCKED on GET /me/dashboard at level {current_level}, "
                    f"got {dashboard_resp.status_code}"
                )
            checks.append({"step": "dashboard", "status": "ok_locked_403"})

        result_payload: dict[str, Any] = {
            "status": "ok",
            "mode": "full",
            "base_url": normalized_base,
            "checks": checks,
        }
        return result_payload
    except httpx.HTTPError as exc:
        raise RuntimeError(f"[{current_step}] {exc}") from exc
    finally:
        if owns_client:
            client.close()
        if cleanup_db and created_user_id and db_url:
            cleanup_summary = _cleanup_test_user(db_url, created_user_id)
            if checks and checks[0].get("status") == "ok":
                checks.append({"step": "cleanup", "deleted": cleanup_summary})


def main() -> int:
    """CLI entrypoint for `infra/scripts/smoke_test.py`."""
    parser = argparse.ArgumentParser(description="Run PaisaProof API smoke tests.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("STAGING_API_URL", "http://localhost:8000/api/v1"),
        help="API base URL (origin or /api/v1 base).",
    )
    parser.add_argument(
        "--jwt",
        default=os.getenv("SMOKE_TEST_JWT"),
        help="Optional pre-minted Neon Auth Bearer JWT.",
    )
    parser.add_argument(
        "--fresh-user",
        action="store_true",
        help="Create a fresh Neon Auth user via sign-up before running checks.",
    )
    parser.add_argument(
        "--auth-base-url",
        default=os.getenv("SMOKE_AUTH_BASE_URL") or os.getenv("NEON_AUTH_BASE_URL"),
        help="Auth base URL for sign-up/sign-in (e.g. https://<app>.vercel.app/api/auth).",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("SMOKE_TEST_EMAIL"),
        help="Neon Auth smoke test user email.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("SMOKE_TEST_PASSWORD"),
        help="Neon Auth smoke test user password.",
    )
    parser.add_argument(
        "--origin",
        default=os.getenv("SMOKE_TEST_ORIGIN", "http://localhost:3000"),
        help="Origin header sent to Neon Auth.",
    )
    parser.add_argument(
        "--health-only",
        action="store_true",
        help="Verify public /health and unauthenticated /me 401 guard without a JWT.",
    )
    parser.add_argument(
        "--platform-only",
        action="store_true",
        help="Verify only platform /health and /me (C1 gate).",
    )
    parser.add_argument(
        "--max-stale-days",
        type=int,
        default=int(os.getenv("MARKET_DATA_MAX_STALE_DAYS", "5")),
        help="Fail /health if market_data_as_of is older than this many days (0 disables).",
    )
    parser.add_argument(
        "--cleanup-db",
        action="store_true",
        help="Delete the temporary --fresh-user rows from Postgres after run.",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    try:
        result = run_smoke_test(
            base_url=args.base_url,
            jwt_token=args.jwt,
            fresh_user=args.fresh_user,
            neon_auth_base_url=args.auth_base_url,
            origin=args.origin,
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY"),
            email=args.email,
            password=args.password,
            health_only=args.health_only,
            platform_only=args.platform_only,
            max_stale_days=args.max_stale_days,
            cleanup_db=args.cleanup_db,
            db_url=os.getenv("DATABASE_URL_UNPOOLED") or os.getenv("DATABASE_URL"),
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
