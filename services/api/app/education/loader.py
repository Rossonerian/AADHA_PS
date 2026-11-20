"""YAML content loader for data/seed/education/*.yaml with strict validation & guardrails."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from ..core import guardrails
from .enums import DataOrigin, SkillArea
from .repository import EducationRepository


VALID_SKILLS = {s.value for s in SkillArea}
VALID_ORIGINS = {o.value for o in DataOrigin}


@dataclass
class LoadSummary:
    questions: int = 0
    lessons: int = 0
    scenarios: int = 0
    explain_records: int = 0
    study_attempts: int = 0


def _assert_origin(record: Dict[str, Any], kind: str) -> str:
    origin = record.get("data_origin")
    if origin not in VALID_ORIGINS:
        raise ValueError(
            f"{kind} '{record.get('id') or record.get('symbol')}' missing valid data_origin "
            f"(expected 'real' or 'synthetic', got {origin!r})"
        )
    return origin


def _assert_guardrails(text: str, field_name: str, rec_id: str) -> str:
    res = guardrails.check_output(text)
    if not res.ok:
        raise ValueError(
            f"Guardrail violation in {rec_id}.{field_name}: {res.reasons}"
        )
    return res.text


def load_yaml_file(repo: EducationRepository, file_path: Union[str, Path]) -> LoadSummary:
    """Loads a single YAML seed file (questions, lessons, scenarios, explain, or study_seed)."""
    path = Path(file_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    summary = LoadSummary()

    for q in raw.get("questions", []):
        _assert_origin(q, "question")
        if q.get("skill_area") not in VALID_SKILLS:
            raise ValueError(f"Invalid skill_area in question {q.get('id')}: {q.get('skill_area')}")
        if not (1 <= int(q["level"]) <= 4):
            raise ValueError(f"Invalid level in question {q.get('id')}: {q.get('level')}")
        if not (1 <= int(q["difficulty"]) <= 5):
            raise ValueError(f"Invalid difficulty in question {q.get('id')}: {q.get('difficulty')}")
        if q["answer"] not in q["options"]:
            raise ValueError(f"Question {q.get('id')} answer must be one of options")
        q["explanation"] = _assert_guardrails(q["explanation"], "explanation", q["id"])
        repo.upsert_question(q)
        summary.questions += 1

    for lesson in raw.get("lessons", []):
        _assert_origin(lesson, "lesson")
        if lesson.get("skill_area") not in VALID_SKILLS:
            raise ValueError(f"Invalid skill_area in lesson {lesson.get('id')}")
        if len(lesson.get("check_questions", [])) < 3:
            raise ValueError(f"Lesson {lesson.get('id')} must have >= 3 check_questions")
        for sec in lesson.get("sections", []):
            _assert_guardrails(sec.get("body", ""), "section.body", lesson["id"])
        for cq in lesson.get("check_questions", []):
            if cq["answer"] not in cq["options"]:
                raise ValueError(f"Lesson {lesson['id']} check question {cq['id']} answer not in options")
            _assert_guardrails(cq.get("explanation", ""), "check_question.explanation", lesson["id"])
        repo.upsert_lesson(lesson)
        summary.lessons += 1

    for sc in raw.get("scenarios", []):
        _assert_origin(sc, "scenario")
        if int(sc["window_days"]) <= 0:
            raise ValueError(f"Scenario {sc.get('id')} window_days must be > 0")
        if not (1 <= int(sc["difficulty"]) <= 5):
            raise ValueError(f"Scenario {sc.get('id')} difficulty must be 1-5")
        sc["explanation"] = _assert_guardrails(sc["explanation"], "explanation", sc["id"])
        repo.upsert_scenario(sc)
        summary.scenarios += 1

    for exp in raw.get("explain_stocks", []):
        _assert_origin(exp, "explain_stock")
        for mv in exp.get("moves", []):
            events = mv.get("events", [])
            if not events:
                raise ValueError(f"Explain {exp['symbol']} {exp['year']} move {mv.get('date')} missing events")
            for ev in events:
                if not ev.get("source") or not str(ev["source"]).strip():
                    raise ValueError(f"Explain {exp['symbol']} {exp['year']} event missing source")
        exp["summary"] = _assert_guardrails(exp["summary"], "summary", f"{exp['symbol']}_{exp['year']}")
        repo.upsert_explain(exp)
        summary.explain_records += 1

    for att in raw.get("study_attempts", []):
        repo.ensure_user(att["user_id"], name=att.get("user_name", att["user_id"]), level=att.get("level", 1))
        repo.record_attempt(
            user_id=att["user_id"],
            item_type=att["item_type"],
            item_id=att["item_id"],
            answer=att["answer"],
            confidence=int(att["confidence"]),
            correct=bool(att["correct"]),
            context=att["context"],
            created_at=att.get("created_at"),
        )
        summary.study_attempts += 1

    return summary


def load_seed_directory(repo: EducationRepository, directory: Optional[Union[str, Path]] = None) -> LoadSummary:
    """Loads all *.yaml files from data/seed/education/ in deterministic sorted order."""
    seed_dir = (
        Path(directory)
        if directory is not None
        else Path(__file__).resolve().parents[4] / "data" / "seed" / "education"
    )
    total = LoadSummary()
    if not seed_dir.exists():
        return total
    for yaml_path in sorted(seed_dir.glob("*.yaml")):
        part = load_yaml_file(repo, yaml_path)
        total.questions += part.questions
        total.lessons += part.lessons
        total.scenarios += part.scenarios
        total.explain_records += part.explain_records
        total.study_attempts += part.study_attempts
    return total
