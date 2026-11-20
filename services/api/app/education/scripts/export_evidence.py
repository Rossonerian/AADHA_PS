"""Phase 6 Evidence Export Script.

Outputs pre/post score, Brier delta, and red-flag delta with 95% CIs.

Usage:
    python3 -m services.api.app.education.scripts.export_evidence \
        --db path/to.db --out-dir ./evidence_out
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from ..enums import AttemptContext, AttemptItemType
from ..loader import load_seed_directory
from ..repository import EducationRepository, apply_migrations
from ..scoring import compute_brier_score, paired_ci_95

RED_FLAG_TAGS = {
    "red_flag",
    "pump_and_dump",
    "governance_fraud",
    "surveillance_list",
    "hype_no_fundamentals",
    "auditor_resignation",
}
REPO_ROOT = Path(__file__).resolve().parents[5]


def _synthetic_study_user_ids() -> set[str]:
    """Read the explicitly seeded study cohort so it cannot be reported as real."""
    seed_path = REPO_ROOT / "data" / "seed" / "education" / "study_seed.yaml"
    if not seed_path.exists():
        return set()
    payload = yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}
    return {
        str(attempt["user_id"])
        for attempt in payload.get("study_attempts", [])
        if attempt.get("user_id")
    }


def _cohort_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate paired metrics and CIs for a single provenance cohort."""
    n = len(rows)
    if not n:
        return {"cohort_n": 0, "metrics": {}}
    return {
        "cohort_n": n,
        "metrics": {
            "score_pct": {
                "pre_mean": round(sum(x["pre_score_pct"] for x in rows) / n, 2),
                "post_mean": round(sum(x["post_score_pct"] for x in rows) / n, 2),
                "delta": paired_ci_95([x["score_delta_pct"] for x in rows]),
            },
            "brier_score": {
                "pre_mean": round(sum(x["pre_brier"] for x in rows) / n, 4),
                "post_mean": round(sum(x["post_brier"] for x in rows) / n, 4),
                "delta": paired_ci_95([x["brier_delta"] for x in rows]),
            },
            "red_flag_detection_pct": {
                "pre_mean": round(sum(x["pre_red_flag_pct"] for x in rows) / n, 2),
                "post_mean": round(sum(x["post_red_flag_pct"] for x in rows) / n, 2),
                "delta": paired_ci_95([x["red_flag_delta_pct"] for x in rows]),
            },
        },
    }


def compute_evidence_report(repo: EducationRepository) -> dict[str, Any]:
    """Compute separate 95% CIs for seeded synthetic and real paired participants."""
    pre_attempts = repo.list_attempts(context=AttemptContext.STUDY_PRE.value)
    post_attempts = repo.list_attempts(context=AttemptContext.STUDY_POST.value)

    # Pre-load item tags for red-flag detection classification
    q_tags = {q["id"]: set(q.get("tags", [])) for q in repo.list_questions()}
    s_tags = {s["id"]: set(s.get("tags", [])) for s in repo.list_scenarios()}

    def is_red_flag(att: dict[str, Any]) -> bool:
        if att["item_type"] == AttemptItemType.QUESTION.value:
            return bool(q_tags.get(att["item_id"], set()) & RED_FLAG_TAGS)
        if att["item_type"] == AttemptItemType.SCENARIO.value:
            return bool(s_tags.get(att["item_id"], set()) & RED_FLAG_TAGS)
        return False

    pre_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    post_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in pre_attempts:
        pre_by_user[a["user_id"]].append(a)
    for a in post_attempts:
        post_by_user[a["user_id"]].append(a)

    paired_users = sorted(set(pre_by_user.keys()) & set(post_by_user.keys()))
    participant_rows: list[dict[str, Any]] = []
    synthetic_users = _synthetic_study_user_ids()

    for uid in paired_users:
        pre_list = pre_by_user[uid]
        post_list = post_by_user[uid]

        pre_acc = 100.0 * sum(1 for x in pre_list if x["correct"]) / len(pre_list)
        post_acc = 100.0 * sum(1 for x in post_list if x["correct"]) / len(post_list)

        pre_brier = compute_brier_score(
            [(int(x["confidence"]), bool(x["correct"])) for x in pre_list]
        )
        post_brier = compute_brier_score(
            [(int(x["confidence"]), bool(x["correct"])) for x in post_list]
        )

        pre_rf_items = [x for x in pre_list if is_red_flag(x)]
        post_rf_items = [x for x in post_list if is_red_flag(x)]
        pre_rf = (
            100.0 * sum(1 for x in pre_rf_items if x["correct"]) / len(pre_rf_items)
            if pre_rf_items
            else 0.0
        )
        post_rf = (
            100.0 * sum(1 for x in post_rf_items if x["correct"]) / len(post_rf_items)
            if post_rf_items
            else 0.0
        )

        d_score = round(post_acc - pre_acc, 4)
        d_brier = round(post_brier - pre_brier, 4)  # Negative means better calibration
        d_rf = round(post_rf - pre_rf, 4)

        participant_rows.append(
            {
                "user_id": uid,
                "data_origin": "synthetic" if uid in synthetic_users else "real",
                "pre_score_pct": round(pre_acc, 2),
                "post_score_pct": round(post_acc, 2),
                "score_delta_pct": round(d_score, 2),
                "pre_brier": round(pre_brier, 4),
                "post_brier": round(post_brier, 4),
                "brier_delta": round(d_brier, 4),
                "pre_red_flag_pct": round(pre_rf, 2),
                "post_red_flag_pct": round(post_rf, 2),
                "red_flag_delta_pct": round(d_rf, 2),
            }
        )

    grouped = {
        origin: [row for row in participant_rows if row["data_origin"] == origin]
        for origin in ("synthetic", "real")
    }
    cohorts = {
        origin: {"data_origin": origin, **_cohort_metrics(rows)}
        for origin, rows in grouped.items()
        if rows
    }
    report: dict[str, Any] = {
        "cohort_n": len(paired_users),
        "cohorts": cohorts,
        "participants": participant_rows,
    }
    if len(cohorts) == 1:
        only_cohort = next(iter(cohorts.values()))
        report["data_origin"] = only_cohort["data_origin"]
        report["metrics"] = only_cohort["metrics"]
    return report


def export_evidence_files(repo: EducationRepository, out_dir: Path) -> dict[str, Any]:
    """Writes evidence_summary.json and evidence_summary.csv to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    report = compute_evidence_report(repo)

    json_path = out_dir / "evidence_summary.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    csv_path = out_dir / "evidence_summary.csv"
    fieldnames = [
        "user_id",
        "data_origin",
        "pre_score_pct",
        "post_score_pct",
        "score_delta_pct",
        "pre_brier",
        "post_brier",
        "brier_delta",
        "pre_red_flag_pct",
        "post_red_flag_pct",
        "red_flag_delta_pct",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["participants"]:
            writer.writerow(row)

    return {"json": json_path, "csv": csv_path, "report": report}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export PaisaProof Education pre/post evidence with 95% CIs."
    )
    parser.add_argument(
        "--db", default=":memory:", help="Path to SQLite DB (default: in-memory seeded)"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Load data/seed/education/*.yaml before export",
    )
    parser.add_argument(
        "--out-dir", default="evidence_output", help="Output directory for CSV & JSON"
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repo = EducationRepository(conn)
    if args.seed or args.db == ":memory:":
        load_seed_directory(repo)

    res = export_evidence_files(repo, Path(args.out_dir))
    r = res["report"]
    cohorts = r.get("cohorts", {})
    if r.get("metrics") and r.get("data_origin"):
        cohorts = {
            r["data_origin"]: {
                "data_origin": r["data_origin"],
                "cohort_n": r["cohort_n"],
                "metrics": r["metrics"],
            }
        }
    if not cohorts:
        print(f"No paired participants found -> {res['csv']} and {res['json']}")
        conn.close()
        return
    print(f"Exported paired participant cohorts -> {res['csv']} and {res['json']}")
    for origin, cohort in cohorts.items():
        sd = cohort["metrics"]["score_pct"]["delta"]
        bd = cohort["metrics"]["brier_score"]["delta"]
        rd = cohort["metrics"]["red_flag_detection_pct"]["delta"]
        print(
            f"  {origin}: N={cohort['cohort_n']} | "
            f"Score {sd['mean']:+.2f}% (95% CI [{sd['ci_low']:+.2f}, {sd['ci_high']:+.2f}]) | "
            f"Brier {bd['mean']:+.4f} (95% CI [{bd['ci_low']:+.4f}, {bd['ci_high']:+.4f}]) | "
            f"Red-flag {rd['mean']:+.2f}% "
            f"(95% CI [{rd['ci_low']:+.2f}, {rd['ci_high']:+.2f}])"
        )
    conn.close()


if __name__ == "__main__":
    main()
