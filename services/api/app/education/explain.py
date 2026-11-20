"""Phase 6: Explain a Stock (~30 stocks), Skill Dashboard, and Study Mode.

Study Mode covers the study_pre / study_post contexts.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from ..core import guardrails, market
from .config import DEFAULT_CONFIG, EducationConfig
from .enums import AttemptContext, AttemptItemType, ToolName
from .exceptions import NotFoundError, ValidationDomainError
from .learning import get_user_unlocks, require_tool_unlocked
from .repository import EducationRepository
from .scenarios import build_public_scenario, recompute_scenario_outcome
from .scoring import compute_brier_score


def explain_stock(
    repo: EducationRepository,
    user_id: str,
    user_level: int,
    symbol: str,
    year: int,
) -> dict[str, Any]:
    """Returns precomputed historical stock explanation with cited events & guardrailed summary.

    Requires Level 2 unlock (`explain_stock`) per SoT Section 8.
    """
    require_tool_unlocked(repo, user_id, ToolName.EXPLAIN_STOCK, user_level=user_level)
    # Historical explanations are keyed by the ticker in use that year (e.g. TATAMOTORS),
    # which alias resolution may map to a successor (TMPV); try the given ticker first.
    resolved = symbol.strip().upper().replace(".NS", "")
    rec = repo.get_explain(resolved, int(year))
    if not rec:
        resolved = market.resolve_symbol(symbol) or resolved
        rec = repo.get_explain(resolved, int(year))
    if not rec:
        raise NotFoundError(
            "EXPLAIN_NOT_FOUND",
            f"No precomputed historical explanation found for '{resolved}' in year {year}.",
        )

    # Verify every event has a non-empty source and pass summary through core.guardrails
    validated_moves: list[dict[str, Any]] = []
    for mv in rec["moves"]:
        events = []
        for ev in mv.get("events", []):
            src = str(ev.get("source", "")).strip()
            if not src:
                raise ValidationDomainError(
                    "MISSING_EVENT_SOURCE",
                    f"Event on {mv.get('date')} for {resolved} is missing a source citation.",
                )
            events.append(
                {"text": guardrails.check_output(ev["text"]).text, "source": src}
            )
        validated_moves.append(
            {"date": mv["date"], "pct": float(mv["pct"]), "events": events}
        )

    safe_summary = guardrails.check_output(rec["summary"]).text
    return {
        "symbol": rec["symbol"],
        "year": int(rec["year"]),
        "chart": rec["chart"],
        "moves": validated_moves,
        "summary": safe_summary,
        "data_origin": rec["data_origin"],
    }


def get_dashboard(
    repo: EducationRepository,
    user_id: str,
    user_level: int,
) -> dict[str, Any]:
    """Returns GET /me/dashboard skill progression, Brier history, and scenario accuracy.

    Requires Level 4 unlock (`dashboard`) per SoT Section 8.
    """
    require_tool_unlocked(repo, user_id, ToolName.DASHBOARD, user_level=user_level)
    unlocks = get_user_unlocks(repo, user_id, user_level=user_level)

    # 1. Group skill_scores by measurement timestamp for clean time-series charts
    history = repo.get_skill_history(user_id)
    by_ts: dict[str, dict[str, Any]] = {}
    for row in history:
        ts = row["measured_at"]
        if ts not in by_ts:
            by_ts[ts] = {"measured_at": ts, "brier": row["brier"], "skills": {}}
        by_ts[ts]["skills"][row["skill_area"]] = round(float(row["score"]), 2)
        by_ts[ts]["brier"] = round(float(row["brier"]), 4)

    skills_over_time = [
        {"measured_at": ts, **data["skills"]} for ts, data in by_ts.items()
    ]
    brier_over_time = [
        {"measured_at": ts, "brier": data["brier"]} for ts, data in by_ts.items()
    ]

    # 2. Scenario accuracy breakdown by difficulty and overall
    scen_attempts = repo.list_attempts(
        user_id=user_id, item_type=AttemptItemType.SCENARIO.value
    )
    by_diff: dict[int, list[bool]] = defaultdict(list)
    for att in scen_attempts:
        sc = repo.get_scenario(att["item_id"])
        diff = int(sc["difficulty"]) if sc else 0
        by_diff[diff].append(bool(att["correct"]))

    scenario_accuracy = []
    for diff in sorted(by_diff.keys()):
        outcomes = by_diff[diff]
        acc = round(100.0 * sum(1 for x in outcomes if x) / len(outcomes), 1)
        scenario_accuracy.append(
            {
                "difficulty": diff,
                "attempts": len(outcomes),
                "accuracy_pct": acc,
            }
        )

    return {
        "level": user_level,
        "unlocks": unlocks,
        "skills_over_time": skills_over_time,
        "brier_over_time": brier_over_time,
        "scenario_accuracy": scenario_accuracy,
    }


def start_study_session(
    repo: EducationRepository,
    user_id: str,
    context: str,
    cfg: EducationConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Starts a study_pre or study_post evaluation session strictly from unseen items."""
    if context not in (AttemptContext.STUDY_PRE.value, AttemptContext.STUDY_POST.value):
        raise ValidationDomainError(
            "INVALID_STUDY_CONTEXT",
            "Study context must be 'study_pre' or 'study_post'.",
        )

    repo.ensure_user(user_id)
    seen_q = repo.list_seen_item_ids(user_id, AttemptItemType.QUESTION.value)
    seen_s = repo.list_seen_item_ids(user_id, AttemptItemType.SCENARIO.value)

    unseen_qs = repo.list_questions(exclude_ids=seen_q)
    # Prioritize a balanced mix including red_flag questions for study measurement
    red_flag_qs = [q for q in unseen_qs if "red_flag" in q.get("tags", [])]
    other_qs = [q for q in unseen_qs if "red_flag" not in q.get("tags", [])]
    half = cfg.study_question_count // 2
    selected_qs = (
        red_flag_qs[:half]
        + other_qs[: (cfg.study_question_count - len(red_flag_qs[:half]))]
    )
    if len(selected_qs) < cfg.study_question_count:
        remaining = [
            q for q in unseen_qs if q["id"] not in {x["id"] for x in selected_qs}
        ]
        selected_qs.extend(remaining[: (cfg.study_question_count - len(selected_qs))])

    unseen_scens = repo.list_scenarios(exclude_ids=seen_s)[: cfg.study_scenario_count]
    if (
        len(selected_qs) < cfg.study_question_count
        or len(unseen_scens) < cfg.study_scenario_count
    ):
        raise ValidationDomainError(
            "INSUFFICIENT_STUDY_ITEMS", "Not enough unseen items for study session."
        )

    items_public = []
    specs = []
    for q in selected_qs:
        items_public.append(
            {
                "item_id": q["id"],
                "item_type": AttemptItemType.QUESTION.value,
                "prompt": {
                    "id": q["id"],
                    "skill_area": q["skill_area"],
                    "difficulty": q["difficulty"],
                    "text": q["text"],
                    "options": q["options"],
                    "data_origin": q.get("data_origin", "synthetic"),
                },
            }
        )
        specs.append(
            {
                "item_id": q["id"],
                "item_type": AttemptItemType.QUESTION.value,
                "is_red_flag": "red_flag" in q.get("tags", []),
            }
        )

    for sc in unseen_scens:
        items_public.append(
            {
                "item_id": sc["id"],
                "item_type": AttemptItemType.SCENARIO.value,
                "prompt": build_public_scenario(sc),
            }
        )
        specs.append(
            {
                "item_id": sc["id"],
                "item_type": AttemptItemType.SCENARIO.value,
                "is_red_flag": bool(
                    set(sc.get("tags", []))
                    & {
                        "pump_and_dump",
                        "governance_fraud",
                        "surveillance_list",
                        "hype_no_fundamentals",
                        "auditor_resignation",
                    }
                ),
            }
        )

    session_id = f"std_{uuid.uuid4().hex[:16]}"
    repo.create_session(
        session_id=session_id,
        user_id=user_id,
        session_type=context,
        state={"context": context, "items": specs},
    )
    return {"session_id": session_id, "context": context, "items": items_public}


def submit_study_session(
    repo: EducationRepository,
    user_id: str,
    session_id: str,
    answers: list[dict[str, Any]],
    cfg: EducationConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Grades a study_pre or study_post session and stores attempts for evidence export."""
    session = repo.get_session(session_id)
    if not session or session["session_type"] not in (
        AttemptContext.STUDY_PRE.value,
        AttemptContext.STUDY_POST.value,
    ):
        raise NotFoundError(
            "STUDY_SESSION_NOT_FOUND", f"Study session '{session_id}' not found."
        )
    if session["user_id"] != user_id:
        raise NotFoundError(
            "STUDY_SESSION_NOT_FOUND", "Study session does not belong to current user."
        )
    if session["completed"]:
        raise ValidationDomainError(
            "STUDY_ALREADY_SUBMITTED", "Study session already submitted."
        )

    context = session["state"]["context"]
    spec_map = {item["item_id"]: item for item in session["state"]["items"]}
    if len(answers) != len(spec_map):
        raise ValidationDomainError(
            "INCOMPLETE_SUBMISSION", f"Expected {len(spec_map)} answers."
        )

    correct = 0
    rf_correct = 0
    rf_total = 0
    brier_pairs = []

    for ans in answers:
        item_id = ans["item_id"]
        spec = spec_map.get(item_id)
        if not spec:
            raise ValidationDomainError(
                "UNKNOWN_ITEM", f"Unknown study item '{item_id}'."
            )
        conf = int(ans["confidence"])
        user_ans = str(ans["answer"]).strip()
        if spec["item_type"] == AttemptItemType.QUESTION.value:
            q = repo.get_question(item_id)
            if not q:
                raise NotFoundError(
                    "QUESTION_NOT_FOUND", f"Question '{item_id}' not found."
                )
            is_correct = user_ans == str(q["answer"]).strip()
        else:
            sc = repo.get_scenario(item_id)
            if not sc:
                raise NotFoundError(
                    "SCENARIO_NOT_FOUND", f"Scenario '{item_id}' not found."
                )
            out = recompute_scenario_outcome(
                sc["symbol"], sc["as_of_date"], sc["window_days"], cfg=cfg
            )
            is_correct = user_ans.lower() == out["actual_direction"]

        if is_correct:
            correct += 1
        if spec["is_red_flag"]:
            rf_total += 1
            if is_correct:
                rf_correct += 1

        repo.record_attempt(
            user_id=user_id,
            item_type=spec["item_type"],
            item_id=item_id,
            answer=user_ans,
            confidence=conf,
            correct=is_correct,
            context=context,
        )
        brier_pairs.append((conf, is_correct))

    score_pct = round(100.0 * correct / len(spec_map), 2)
    brier = compute_brier_score(brier_pairs)
    rf_pct = round(100.0 * rf_correct / rf_total, 2) if rf_total > 0 else 0.0

    state = dict(session["state"])
    state["result"] = {
        "score_pct": score_pct,
        "brier": brier,
        "red_flag_accuracy_pct": rf_pct,
    }
    repo.update_session(session_id, state, completed=True)

    return {
        "session_id": session_id,
        "context": context,
        "score_pct": score_pct,
        "brier": brier,
        "red_flag_accuracy_pct": rf_pct,
        "total_items": len(spec_map),
    }
