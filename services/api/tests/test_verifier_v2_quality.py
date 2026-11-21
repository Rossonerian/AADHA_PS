"""Historical facts, monotonicity, independent validation and rating isolation."""

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
from itertools import product
from pathlib import Path

import pandas as pd
import pytest

from app.core.guardrails import check_output
from app.verifier.ports import VerifierCore
from app.verifier.provider_profile import enforcement
from app.verifier.schemas import DataOrigin
from app.verifier.scoring import rate_source
from app.verifier.tip_quality import compute, facts

POSTED = date(2025, 1, 20)


class HistoricalMarket:
    def __init__(self, periods=120, volume=True):
        self.stock = pd.DataFrame(
            {"close": 100.0, "open": 100.0},
            index=pd.bdate_range(end=POSTED - timedelta(days=1), periods=periods),
        )
        if volume:
            self.stock["volume"] = 1000.0
        self.benchmark = self.stock[["close", "open"]].copy()
        self.stage = None

    def prices(self, symbol, start, end):
        assert end < POSTED
        return self.stock.copy()  # Deliberately ignores end: the consumer must filter.

    def index(self, name, start, end):
        assert end < POSTED
        return self.benchmark.copy()

    def surveillance(self, symbol, as_of):
        assert as_of < POSTED
        return self.stage


def evaluate(market, **changes):
    core = VerifierCore(
        lambda *_: pytest.fail("Facts cannot call the model"),
        check_output,
        market,
        market_cap_bucket=lambda symbol, day: "small_cap",
    )
    args = dict(
        symbol="TCS",
        direction="up",
        target=120.0,
        stop=90.0,
        window=5,
        posted=POSTED,
        core=core,
        origin=DataOrigin.SYNTHETIC,
    )
    args.update(changes)
    return compute(**args), core


def test_all_historical_signals_and_fact_templates():
    market = HistoricalMarket()
    market.stock.iloc[-5:, market.stock.columns.get_loc("volume")] = 3000
    market.stage = "ASM1"
    q, core = evaluate(market)
    s = q["signals"]
    assert s["required_move_pct"] == pytest.approx(20)
    assert s["move_base_rate"] == 0
    assert s["pre_post_run_up_pct"] == 0
    assert s["pre_post_volume_ratio"] == 3
    assert s["illiquid_small_cap"] is True
    assert s["surveillance_list"] == "ASM1"
    assert s["stop_distance_pct"] == 10
    assert s["reward_risk"] == 2
    assert 0 <= q["tip_quality_score"] <= 1
    shown = facts(q, core)
    assert len(shown) == 8
    assert all(check_output(r["text"]).ok for r in shown)
    assert "tip_quality_score" not in str(shown)


def test_future_and_same_day_poison_cannot_change_any_signal_or_score():
    market = HistoricalMarket()
    before, _ = evaluate(market)
    future = pd.DataFrame(
        {"close": 1e12, "open": 0.001, "volume": 1e12},
        index=pd.bdate_range(POSTED, periods=300),
    )
    market.stock = pd.concat([market.stock, future])
    market.benchmark = pd.concat([market.benchmark, future])
    after, _ = evaluate(market)
    assert before == after


@pytest.mark.parametrize("target,stop", [(None, None), (120.0, None), (None, 90.0)])
def test_missing_levels_do_not_create_risk_ratios(target, stop):
    q, _ = evaluate(HistoricalMarket(), target=target, stop=stop)
    assert q["signals"]["stop_distance_pct"] is None
    assert q["signals"]["reward_risk"] is None
    if target is None:
        assert q["signals"]["required_move_pct"] is None


def test_missing_history_volume_publication_and_adjustment_basis():
    q, _ = evaluate(HistoricalMarket(periods=3, volume=False))
    for key in (
        "pre_post_volume_ratio",
        "move_base_rate",
        "illiquid_small_cap",
        "pre_post_run_up_pct",
    ):
        assert q["signals"][key] is None
    q, _ = evaluate(HistoricalMarket(), posted=None)
    assert q["tip_quality_score"] is None and all(
        v is None for v in q["signals"].values()
    )
    market = HistoricalMarket()
    market.stock["adj close"] = 80.0
    q, _ = evaluate(market)
    assert q["signals"]["required_move_pct"] is None
    assert q["signals"]["reward_risk"] is None


def test_real_nominal_comparisons_require_evidence_and_bad_volume_is_unknown():
    from dataclasses import replace

    market = HistoricalMarket()
    q, bindings = evaluate(market, origin=DataOrigin.REAL)
    assert q["signals"]["required_move_pct"] is None
    proven = replace(bindings, nominal_price_basis=lambda *args: True)
    q, _ = evaluate(market, origin=DataOrigin.REAL, core=proven)
    assert q["signals"]["required_move_pct"] == pytest.approx(20)
    market.stock["volume"] = float("inf")
    q, _ = evaluate(market)
    assert q["signals"]["pre_post_volume_ratio"] is None
    assert q["signals"]["illiquid_small_cap"] is None
    assert 0 <= q["tip_quality_score"] <= 1


def test_harder_target_higher_volume_and_runup_cannot_improve_quality():
    market = HistoricalMarket()
    base, _ = evaluate(market)
    harder, _ = evaluate(market, target=140.0, stop=None)
    comparable, _ = evaluate(market, target=120.0, stop=None)
    assert harder["tip_quality_score"] <= comparable["tip_quality_score"]
    market.stock.iloc[-5:, market.stock.columns.get_loc("volume")] = 9000
    spiked, _ = evaluate(market)
    assert spiked["tip_quality_score"] <= base["tip_quality_score"]


def test_short_direction_and_no_target_relative_windows():
    market = HistoricalMarket()
    q, _ = evaluate(market, direction="down", target=80.0, stop=110.0)
    assert q["signals"]["required_move_pct"] == pytest.approx(-20)
    assert q["signals"]["reward_risk"] == 2
    market.stock["close"] = [100 + n for n in range(len(market.stock))]
    q, _ = evaluate(market, target=None, stop=None)
    assert q["signals"]["move_base_rate"] == 1


def legacy(*, scored, correct, tracked, deleted, registered, flagged):
    from fractions import Fraction as F

    scored, tracked = max(0, scored), max(0, tracked)
    track = F(2 + min(scored, max(0, correct)), scored + 4)
    kept = F(tracked - min(tracked, max(0, deleted)), tracked) if tracked else F(1, 2)
    clean = F(tracked - min(tracked, max(0, flagged)), tracked) if tracked else F(1, 2)
    reg = F(1, 2) if registered is None else F(int(registered))
    return round(60 * track + F(25, 2) * (kept + reg) + 15 * clean)


def test_weight_zero_golden_against_original_formula():
    for scored, tracked, registered, flagged in product(
        (0, 1, 4, 5, 30), (0, 5, 40), (None, False, True), (0, 3, 100)
    ):
        args = dict(
            scored=scored,
            correct=scored // 2,
            tracked=tracked,
            deleted=2,
            registered=registered,
            flagged=flagged,
        )
        expected = legacy(**args)
        assert rate_source(**args, tip_quality=0, tip_quality_weight=0)[0] == expected
        assert rate_source(**args, tip_quality=1, tip_quality_weight=0)[0] == expected


def test_enforcement_removes_registration_credit_only_and_weight_is_bounded():
    args = dict(scored=10, correct=8, tracked=10, deleted=0, registered=True, flagged=0)
    clean = rate_source(**args)[0]
    enforced = rate_source(**args, enforcement=True)[0]
    assert clean - enforced in (12, 13)
    assert enforced == rate_source(**(args | {"registered": False}))[0]
    with pytest.raises(ValueError):
        rate_source(**args, tip_quality_weight=11)


def test_enforcement_matches_exact_identity_and_preserves_unknown():
    yes, refs = enforcement(
        reg_no="INH200007353",
        legal_name="unrelated alias",
        origin="real",
        as_of=date(2026, 11, 21),
    )
    assert yes is True and len(refs) == 1
    assert (
        enforcement(
            reg_no=None, legal_name="Arun N", origin="real", as_of=date(2026, 11, 21)
        )[0]
        is True
    )
    for name, origin, day in [
        ("Arun", "real", POSTED),
        ("Arun N", "synthetic", date(2026, 11, 21)),
        ("Arun N", "real", date(2024, 1, 1)),
    ]:
        assert enforcement(reg_no=None, legal_name=name, origin=origin, as_of=day) == (
            None,
            [],
        )


def validation_module():
    path = Path(__file__).resolve().parents[3] / "infra/scripts/validate_tip_quality.py"
    spec = importlib.util.spec_from_file_location("tip_quality_validation", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def observations(module, *, invert=False, confounded=False):
    rows = []
    # Every later provider has both outcomes: grouped validation is meaningful.
    for n in range(20):
        for provider in range(30):
            correct = bool(n % 2)
            quality = (
                (0.9 if correct else 0.1) if not invert else (0.1 if correct else 0.9)
            )
            if confounded:
                quality = provider / 30
            rows.append(
                module.Observation(
                    str(provider),
                    datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=n),
                    quality,
                    correct,
                )
            )
    return rows


def test_validation_refuse_pass_fail_and_provider_confounding():
    module = validation_module()
    assert module.validate([])["status"] == "REFUSE"
    assert module.validate(observations(module)[:299])["status"] == "REFUSE"
    passing = module.validate(observations(module))
    assert passing["status"] == "PASS" and passing["test_auc"] == 1
    assert passing["provider_grouped_auc"] == 1 and passing["grouped_providers"] == 30
    assert passing["weight_changed"] is False
    assert sum(b["n"] for b in passing["calibration_buckets"]) == passing["test_claims"]
    assert module.validate(observations(module, invert=True))["status"] == "FAIL"
    assert module.validate(observations(module, confounded=True))["status"] == "FAIL"


def test_validation_cli_reports_uncovered_eligible_claims_without_writing(
    db_session, capsys, monkeypatch
):
    from types import SimpleNamespace
    from uuid import uuid4

    from sqlalchemy import select

    from app.core.models import UserRecord
    from app.verifier.models import Claim, Source, Submission

    owner = uuid4()
    db_session.add(UserRecord(id=str(owner), current_level=1))
    source = Source(platform="broker_research", handle="fixture", data_origin="real")
    db_session.add(source)
    db_session.flush()
    submission = Submission(
        user_id=owner,
        source_id=source.id,
        raw_content="Fixture",
        content_hash="a" * 64,
        captured_at=datetime.now(UTC),
        published_at=datetime(2024, 1, 1, tzinfo=UTC),
        data_origin="real",
    )
    db_session.add(submission)
    db_session.flush()
    claim = Claim(
        submission_id=submission.id,
        window_days=20,
        scorable=True,
        status="scored",
        rating_eligible=True,
        outcome={"correct": True},
        data_origin="real",
    )
    db_session.add(claim)
    db_session.commit()
    module = validation_module()
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(
            database_url=str(db_session.get_bind().url), database_url_unpooled=""
        ),
    )
    assert module.main() == 2
    import json

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "REFUSE"
    assert report["rating_eligible_scored_claims"] == 1
    assert report["quality_covered_claims"] == 0
    db_session.expire_all()
    assert db_session.get(Claim, claim.id).tip_quality is None
    assert db_session.scalar(select(Source.score)) == 0
