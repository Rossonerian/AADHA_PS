"""Nasdaq verifier: gate, Finnhub mapping, scoring and no-recommendation wording."""

import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import finnhub as fh_mod
from app.core.auth import User, current_user
from app.core.finnhub import FinnhubClient, get_finnhub
from app.education.repository import EducationRepository
from app.main import create_app
from app.nasdaq_verifier import service
from app.nasdaq_verifier.gate import (
    GateInputs,
    get_gate_inputs,
    missing_requirements,
    read_gate_inputs,
)

BANNED = ("buy", "sell", "hold", "price target", "strong buy", "analyst")


class FakeFinnhub(FinnhubClient):
    def __init__(self) -> None:
        super().__init__("test-key")

    def _get(self, path: str, **params: Any) -> Any:
        assert path in fh_mod.ALLOWED_ENDPOINTS
        return {
            "/quote": {"c": 190.0, "h": 192.0, "l": 188.0},
            "/stock/profile2": {
                "name": "Apple Inc",
                "finnhubIndustry": "Technology",
                "exchange": "NASDAQ NMS - GLOBAL MARKET",
                "marketCapitalization": 3000000.0,
            },
            "/stock/metric": {
                "metric": {"52WeekHigh": 200.0, "52WeekLow": 150.0, "peTTM": 30.0}
            },
            "/stock/candle": {
                "s": "ok",
                "t": [1700000000, 1700086400],
                "c": [180.0, 190.0],
            },
        }[path]


def _client(user: User, inputs: GateInputs) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[current_user] = lambda: user
    app.dependency_overrides[get_gate_inputs] = lambda: inputs
    app.dependency_overrides[get_finnhub] = FakeFinnhub
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unlocked(migrated_db: str) -> Iterator[TestClient]:
    yield from _client(User(id="u1", level=4), GateInputs(100, 0.2))


@pytest.fixture
def locked(migrated_db: str) -> Iterator[TestClient]:
    yield from _client(User(id="u1", level=3), GateInputs(80, 0.3))


def test_locked_user_gets_403(locked: TestClient) -> None:
    responses = (
        locked.get("/api/v1/nasdaq-verifier/challenge?symbol=AAPL"),
        locked.post(
            "/api/v1/nasdaq-verifier/submit", json={"challenge_id": "x", "answers": []}
        ),
    )
    for r in responses:
        assert r.status_code == 403
        err = r.json()["error"]
        assert err["code"] == "TOOL_LOCKED" and err["required_level"] == 4
        assert set(err["missing_requirements"]) == {
            "level_4",
            "plan_progress_100",
            "brier_lte_0.25",
        }


def test_missing_data_fails_closed(migrated_db: str) -> None:
    c = next(_client(User(id="u1", level=4), GateInputs(None, None)))
    assert c.get("/api/v1/nasdaq-verifier/challenge").status_code == 403


def test_gate_fails_closed_on_nonfinite_or_out_of_range_inputs() -> None:
    user = User(id="00000000-0000-4000-8000-000000000001", level=4)
    assert "brier_lte_0.25" in missing_requirements(
        user, GateInputs(100.0, float("nan"))
    )
    assert "brier_lte_0.25" in missing_requirements(user, GateInputs(100.0, -0.01))
    assert "plan_progress_100" in missing_requirements(
        user, GateInputs(float("inf"), 0.2)
    )


def test_gate_derives_progress_from_education_lesson_checks(db_session: Any) -> None:
    user_id = str(uuid.uuid4())
    repo = EducationRepository(db_session)
    repo.ensure_user(user_id, level=4)
    repo.upsert_plan(
        user_id,
        level=4,
        lesson_ids=["lesson_a", "lesson_b"],
        progress={"lesson_a": "completed", "lesson_b": "not_started"},
    )
    repo.record_skill_scores(user_id, {"risk": 80.0}, brier=0.18)
    user = User(id=user_id, level=4)
    assert repo.is_orm, type(db_session)
    assert repo.get_plan(user_id) is not None

    inputs = read_gate_inputs(db_session, user)
    assert inputs.progress_pct == 50.0
    assert inputs.brier == pytest.approx(0.18)

    repo.upsert_plan(
        user_id,
        level=4,
        lesson_ids=["lesson_a", "lesson_b"],
        progress={"lesson_a": "completed", "lesson_b": "completed"},
    )
    inputs = read_gate_inputs(db_session, user)
    assert inputs.progress_pct == 100.0


def test_unlocked_flow_and_real_origin(unlocked: TestClient) -> None:
    r = unlocked.get("/api/v1/nasdaq-verifier/challenge?symbol=aapl")
    assert r.status_code == 200
    body = r.json()
    assert body["data_origin"] == "real"
    assert body["snapshot"]["data_origin"] == "real"
    assert body["nasdaq_url"] == "https://www.nasdaq.com/market-activity/stocks/aapl"
    assert len(body["snapshot"]["chart"]) == 2
    assert "_answer" not in json.dumps(body)
    qs = body["questions"]
    assert 3 <= len(qs) <= 4
    sub = unlocked.post(
        "/api/v1/nasdaq-verifier/submit",
        json={
            "challenge_id": body["challenge_id"],
            "answers": [
                {"question_id": q["id"], "answer": q["options"][0], "confidence": 60}
                for q in qs
            ],
        },
    )
    assert sub.status_code == 200
    out = sub.json()
    assert 0 <= out["brier"] <= 1 and len(out["results"]) == len(qs)
    again = unlocked.post(
        "/api/v1/nasdaq-verifier/submit",
        json={"challenge_id": body["challenge_id"], "answers": []},
    )
    assert again.status_code == 404


def test_perfect_answers_pass(unlocked: TestClient) -> None:
    body = unlocked.get("/api/v1/nasdaq-verifier/challenge?symbol=AAPL").json()
    key = service._store[body["challenge_id"]].answers
    out = unlocked.post(
        "/api/v1/nasdaq-verifier/submit",
        json={
            "challenge_id": body["challenge_id"],
            "answers": [
                {"question_id": k, "answer": v, "confidence": 90}
                for k, v in key.items()
            ],
        },
    ).json()
    assert out["passed"] and out["score"] == 1.0


def test_no_recommendation_wording(unlocked: TestClient) -> None:
    body = unlocked.get("/api/v1/nasdaq-verifier/challenge?symbol=AAPL").json()
    text = json.dumps([body["questions"], body["snapshot"]["name"]]).lower()
    assert not any(w in text for w in BANNED)
    assert "never recommends" in body["disclaimer"]


def test_endpoint_allowlist_blocks_recommendations() -> None:
    c = FinnhubClient("k")
    for bad in (
        "/stock/recommendation",
        "/stock/price-target",
        "/stock/upgrade-downgrade",
    ):
        with pytest.raises(ValueError):
            c._get(bad, symbol="AAPL")


def test_non_nasdaq_symbol_rejected(
    unlocked: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    orig = FakeFinnhub._get

    def nyse(self: FakeFinnhub, path: str, **p: Any) -> Any:
        d = orig(self, path, **p)
        if path == "/stock/profile2":
            d = {**d, "exchange": "NEW YORK STOCK EXCHANGE, INC."}
        return d

    monkeypatch.setattr(FakeFinnhub, "_get", nyse)
    r = unlocked.get("/api/v1/nasdaq-verifier/challenge?symbol=IBM")
    assert r.status_code == 422 and r.json()["error"]["code"] == "NOT_NASDAQ"


def test_missing_key_is_503() -> None:
    with pytest.raises(fh_mod.FinnhubUnavailableError):
        FinnhubClient("")._get("/quote", symbol="AAPL")
