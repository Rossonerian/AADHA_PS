"""Read-only temporal and within-provider validation; never activates a weight.

The index is fixed, so the early 70% is descriptive training/reference data, not
used to fit a new formula. A timestamp tie never crosses the split. Provider
grouped AUC is the unweighted mean within-provider AUC on the late partition,
requiring both classes for at least half the providers (and at least 15).
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from statistics import mean

from app.core.config import get_settings
from app.verifier.models import Claim, Submission
from app.verifier.tip_quality import VERSION
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Observation:
    provider: str
    published_at: datetime
    quality: float
    correct: bool


def auc(rows: list[Observation]) -> float | None:
    positives = sum(r.correct for r in rows)
    negatives = len(rows) - positives
    if not positives or not negatives:
        return None
    ordered = sorted(rows, key=lambda r: r.quality)
    rank_sum, offset = 0.0, 0
    while offset < len(ordered):
        end = offset + 1
        while end < len(ordered) and ordered[end].quality == ordered[offset].quality:
            end += 1
        rank_sum += ((offset + 1 + end) / 2) * sum(
            r.correct for r in ordered[offset:end]
        )
        offset = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def validate(rows: list[Observation]) -> dict[str, object]:
    providers = {r.provider for r in rows}
    result: dict[str, object] = {
        "claims": len(rows),
        "providers": len(providers),
        "version": VERSION,
        "weight_changed": False,
    }
    if len(rows) < 300 or len(providers) < 30:
        return result | {
            "status": "REFUSE",
            "reason": "Requires >=300 eligible scored claims and >=30 providers",
        }
    if any(not isfinite(r.quality) or not 0 <= r.quality <= 1 for r in rows):
        return result | {"status": "REFUSE", "reason": "Invalid quality values"}
    ordered = sorted(rows, key=lambda r: r.published_at)
    boundary = ordered[int(0.7 * len(ordered))].published_at
    early = [r for r in ordered if r.published_at < boundary]
    late = [r for r in ordered if r.published_at >= boundary]
    if not early or not late:
        return result | {
            "status": "REFUSE",
            "reason": "Insufficient distinct publication times",
        }
    grouped: dict[str, list[Observation]] = defaultdict(list)
    for row in late:
        grouped[row.provider].append(row)
    group_auc = {
        provider: value
        for provider, group in grouped.items()
        if (value := auc(group)) is not None
    }
    macro = mean(group_auc.values()) if group_auc else None
    test_auc = auc(late)
    buckets = []
    for i in range(5):
        group = [r for r in late if min(int(r.quality * 5), 4) == i]
        buckets.append(
            {
                "lower": i / 5,
                "upper": (i + 1) / 5,
                "n": len(group),
                "mean_quality": mean(r.quality for r in group) if group else None,
                "observed_correct_fraction": (
                    mean(r.correct for r in group) if group else None
                ),
            }
        )
    sufficient = len(group_auc) >= max(15, (len(providers) + 1) // 2)
    passed = (
        sufficient
        and test_auc is not None
        and test_auc >= 0.6
        and macro is not None
        and macro >= 0.6
    )
    return result | {
        "status": "PASS" if passed else "FAIL",
        "split_at": boundary.isoformat(),
        "train_claims": len(early),
        "test_claims": len(late),
        "train_auc": auc(early),
        "test_auc": test_auc,
        "provider_grouped_auc": macro,
        "grouped_providers": len(group_auc),
        "per_provider_auc": group_auc,
        "group_coverage_sufficient": sufficient,
        "calibration_buckets": buckets,
    }


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url_unpooled or settings.database_url)
    rows = []
    seen = set()
    eligible = set()
    eligible_providers = set()
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION READ ONLY"))
        for claim, submission in db.execute(
            select(Claim, Submission)
            .join(Submission)
            .where(
                Claim.rating_eligible.is_(True),
                Claim.status == "scored",
                Claim.data_origin == "real",
                Submission.data_origin == "real",
                Submission.published_at.is_not(None),
            )
        ):
            q, outcome = claim.tip_quality or {}, claim.outcome or {}
            quality, correct = q.get("tip_quality_score"), outcome.get("correct")
            identity = (
                submission.source_id,
                submission.post_url or submission.content_hash,
                claim.symbol,
                claim.direction,
                claim.entry,
                claim.target,
                claim.stop,
                claim.window_days,
            )
            eligible.add(identity)
            eligible_providers.add(str(submission.source_id))
            if (
                claim.tip_quality_version != VERSION
                or identity in seen
                or not isinstance(quality, (int, float))
                or not isinstance(correct, bool)
            ):
                continue
            seen.add(identity)
            assert submission.published_at is not None
            rows.append(
                Observation(
                    str(submission.source_id),
                    submission.published_at,
                    float(quality),
                    correct,
                )
            )
    engine.dispose()
    result = validate(rows) | {
        "rating_eligible_scored_claims": len(eligible),
        "rating_eligible_providers": len(eligible_providers),
        "quality_covered_claims": len(rows),
    }
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2 if result["status"] == "REFUSE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
