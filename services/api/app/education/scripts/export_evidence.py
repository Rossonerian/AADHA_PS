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


def compute_evidence_report(repo: EducationRepository) -> dict[str, Any]:
    """Computes paired study_pre vs study_post metrics with 95% Student's t CIs."""
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

    score_deltas: list[float] = []
    brier_deltas: list[float] = []
    rf_deltas: list[float] = []

    pre_scores, post_scores = [], []
    pre_briers, post_briers = [], []
    pre_rfs, post_rfs = [], []

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

        pre_scores.append(pre_acc)
        post_scores.append(post_acc)
        pre_briers.append(pre_brier)
        post_briers.append(post_brier)
        pre_rfs.append(pre_rf)
        post_rfs.append(post_rf)

        score_deltas.append(d_score)
        brier_deltas.append(d_brier)
        rf_deltas.append(d_rf)

        participant_rows.append(
            {
                "user_id": uid,
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

    n = len(paired_users)
    return {
        "cohort_n": n,
        "data_origin": "synthetic",
        "metrics": {
            "score_pct": {
                "pre_mean": round(sum(pre_scores) / n, 2) if n else 0.0,
                "post_mean": round(sum(post_scores) / n, 2) if n else 0.0,
                "delta": paired_ci_95(score_deltas),
            },
            "brier_score": {
                "pre_mean": round(sum(pre_briers) / n, 4) if n else 0.0,
                "post_mean": round(sum(post_briers) / n, 4) if n else 0.0,
                "delta": paired_ci_95(brier_deltas),
            },
            "red_flag_detection_pct": {
                "pre_mean": round(sum(pre_rfs) / n, 2) if n else 0.0,
                "post_mean": round(sum(post_rfs) / n, 2) if n else 0.0,
                "delta": paired_ci_95(rf_deltas),
            },
        },
        "participants": participant_rows,
    }


def export_evidence_files(repo: EducationRepository, out_dir: Path) -> dict[str, Any]:
    """Writes evidence_summary.json and evidence_summary.csv to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    report = compute_evidence_report(repo)

    json_path = out_dir / "evidence_summary.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    csv_path = out_dir / "evidence_summary.csv"
    fieldnames = [
        "user_id",
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
    sd = r["metrics"]["score_pct"]["delta"]
    bd = r["metrics"]["brier_score"]["delta"]
    rd = r["metrics"]["red_flag_detection_pct"]["delta"]
    print(
        f"Exported N={r['cohort_n']} paired participants -> {res['csv']} and {res['json']}\n"
        f"  Score delta:    {sd['mean']:+.2f}% "
        f"(95% CI [{sd['ci_low']:+.2f}, {sd['ci_high']:+.2f}])\n"
        f"  Brier delta:    {bd['mean']:+.4f} "
        f"(95% CI [{bd['ci_low']:+.4f}, {bd['ci_high']:+.4f}])\n"
        f"  Red-flag delta: {rd['mean']:+.2f}% "
        f"(95% CI [{rd['ci_low']:+.2f}, {rd['ci_high']:+.2f}])"
    )
    conn.close()


if __name__ == "__main__":
    main()
