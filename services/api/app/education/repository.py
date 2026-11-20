"""Data access repository for Education module.

Dual-mode architecture:
- Supabase Postgres / SQLAlchemy 2.0 Session (Render production with Hardhik's core.db.get_db())
- Parameterized DB-API / SQLite (offline test harnesses & standalone dev)
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from .models import (
    Attempt,
    EduSession,
    ExplainCache,
    Lesson,
    Plan,
    Question,
    Scenario,
    SkillScore,
    Unlock,
    User,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _migration_sql_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "db" / "migrations" / "sql"


def apply_migrations(conn: Any) -> None:
    """Applies Education DDL on a fresh or existing DB (idempotent)."""
    if isinstance(conn, sqlite3.Connection):
        sql_file = _migration_sql_dir() / "001_education_tables.sql"
        if sql_file.exists():
            ddl = sql_file.read_text(encoding="utf-8")
            conn.executescript(ddl)
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.commit()
    elif hasattr(conn, "get_bind"):
        from .models import Base
        Base.metadata.create_all(bind=conn.get_bind())


def revert_migrations(conn: Any) -> None:
    """Drops Education tables cleanly (for rollback tests)."""
    if isinstance(conn, sqlite3.Connection):
        sql_file = _migration_sql_dir() / "001_education_tables_down.sql"
        if sql_file.exists():
            ddl = sql_file.read_text(encoding="utf-8")
            conn.executescript(ddl)
            conn.commit()
    elif hasattr(conn, "get_bind"):
        from .models import Base
        Base.metadata.drop_all(bind=conn.get_bind())


class EducationRepository:
    """Encapsulates all relational persistence for Education tables."""

    def __init__(self, conn: Any):
        self.conn = conn
        self.is_orm: bool = isinstance(conn, Session) or (
            hasattr(conn, "scalars") and hasattr(conn, "commit") and not isinstance(conn, sqlite3.Connection)
        )

    # ---- Users (read/upsert helper for Hardhik's users table) ----

    def ensure_user(self, user_id: str, name: str = "Learner", level: int = 1) -> Dict[str, Any]:
        if self.is_orm:
            user = self.conn.get(User, user_id)
            if user:
                return {"id": user.id, "name": user.name, "current_level": user.current_level}
            user = User(id=user_id, name=name, current_level=int(level))
            self.conn.add(user)
            self.conn.commit()
            return {"id": user_id, "name": name, "current_level": level}

        row = self.conn.execute(
            "SELECT id, name, current_level, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row:
            return dict(row)
        self.conn.execute(
            "INSERT INTO users (id, name, current_level, created_at) VALUES (?, ?, ?, ?)",
            (user_id, name, level, utc_now_iso()),
        )
        self.conn.commit()
        return {"id": user_id, "name": name, "current_level": level}

    def get_user_level(self, user_id: str, default_level: int = 1) -> int:
        if self.is_orm:
            user = self.conn.get(User, user_id)
            return int(user.current_level) if user else default_level

        row = self.conn.execute(
            "SELECT current_level FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return int(row["current_level"]) if row else default_level

    def set_user_level(self, user_id: str, level: int) -> None:
        if self.is_orm:
            user = self.conn.get(User, user_id)
            if not user:
                user = User(id=user_id, name="Learner", current_level=int(level))
                self.conn.add(user)
            else:
                user.current_level = int(level)
            self.conn.commit()
            return

        self.ensure_user(user_id, level=level)
        self.conn.execute(
            "UPDATE users SET current_level = ? WHERE id = ?",
            (int(level), user_id),
        )
        self.conn.commit()

    # ---- Unlocks ----

    def list_unlocks(self, user_id: str) -> List[str]:
        if self.is_orm:
            stmt = select(Unlock.tool).where(Unlock.user_id == user_id).order_by(Unlock.id.asc())
            return list(self.conn.scalars(stmt).all())

        rows = self.conn.execute(
            "SELECT tool FROM unlocks WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
        return [r["tool"] for r in rows]

    def grant_unlocks(self, user_id: str, tools: Sequence[str]) -> List[str]:
        """Idempotently grants tools and returns only newly granted tools."""
        self.ensure_user(user_id)
        existing = set(self.list_unlocks(user_id))
        newly_granted: List[str] = []

        if self.is_orm:
            for tool in tools:
                if tool not in existing:
                    u = Unlock(user_id=user_id, tool=tool)
                    self.conn.add(u)
                    newly_granted.append(tool)
                    existing.add(tool)
            self.conn.commit()
            return newly_granted

        now = utc_now_iso()
        for tool in tools:
            if tool not in existing:
                self.conn.execute(
                    "INSERT OR IGNORE INTO unlocks (user_id, tool, unlocked_at) VALUES (?, ?, ?)",
                    (user_id, tool, now),
                )
                newly_granted.append(tool)
                existing.add(tool)
        self.conn.commit()
        return newly_granted

    # ---- Skill Scores ----

    def record_skill_scores(
        self,
        user_id: str,
        skill_scores: Dict[str, float],
        brier: float,
        measured_at: Optional[str] = None,
    ) -> None:
        self.ensure_user(user_id)
        if self.is_orm:
            m_dt = datetime.fromisoformat(measured_at) if measured_at else datetime.now(timezone.utc)
            for area, score in skill_scores.items():
                sc = SkillScore(
                    user_id=user_id,
                    skill_area=area,
                    score=float(score),
                    brier=float(brier),
                    measured_at=m_dt,
                )
                self.conn.add(sc)
            self.conn.commit()
            return

        ts = measured_at or utc_now_iso()
        for area, score in skill_scores.items():
            self.conn.execute(
                "INSERT INTO skill_scores (user_id, skill_area, score, brier, measured_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, area, float(score), float(brier), ts),
            )
        self.conn.commit()

    def get_latest_skill_scores(self, user_id: str) -> Dict[str, float]:
        if self.is_orm:
            subq = (
                select(SkillScore.skill_area, func.max(SkillScore.id).label("max_id"))
                .where(SkillScore.user_id == user_id)
                .group_by(SkillScore.skill_area)
                .subquery()
            )
            stmt = select(SkillScore.skill_area, SkillScore.score).join(subq, SkillScore.id == subq.c.max_id)
            rows = self.conn.execute(stmt).all()
            return {r[0]: float(r[1]) for r in rows}

        rows = self.conn.execute(
            """
            SELECT s.skill_area, s.score
            FROM skill_scores s
            INNER JOIN (
                SELECT skill_area, MAX(id) AS max_id
                FROM skill_scores
                WHERE user_id = ?
                GROUP BY skill_area
            ) latest ON s.id = latest.max_id
            """,
            (user_id,),
        ).fetchall()
        return {r["skill_area"]: float(r["score"]) for r in rows}

    def get_skill_history(self, user_id: str) -> List[Dict[str, Any]]:
        if self.is_orm:
            stmt = (
                select(SkillScore)
                .where(SkillScore.user_id == user_id)
                .order_by(SkillScore.measured_at.asc(), SkillScore.id.asc())
            )
            scores = self.conn.scalars(stmt).all()
            return [
                {
                    "skill_area": s.skill_area,
                    "score": s.score,
                    "brier": s.brier,
                    "measured_at": s.measured_at.isoformat() if hasattr(s.measured_at, "isoformat") else str(s.measured_at),
                }
                for s in scores
            ]

        rows = self.conn.execute(
            "SELECT skill_area, score, brier, measured_at FROM skill_scores "
            "WHERE user_id = ? ORDER BY measured_at ASC, id ASC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- Questions ----

    def upsert_question(self, q: Dict[str, Any]) -> None:
        if self.is_orm:
            existing = self.conn.get(Question, q["id"])
            if existing:
                existing.level = int(q["level"])
                existing.skill_area = q["skill_area"]
                existing.difficulty = int(q["difficulty"])
                existing.text = q["text"]
                existing.options = q["options"]
                existing.answer = q["answer"]
                existing.explanation = q["explanation"]
                existing.tags = q.get("tags", [])
                existing.data_origin = q.get("data_origin", "synthetic")
            else:
                item = Question(
                    id=q["id"],
                    level=int(q["level"]),
                    skill_area=q["skill_area"],
                    difficulty=int(q["difficulty"]),
                    text=q["text"],
                    options=q["options"],
                    answer=q["answer"],
                    explanation=q["explanation"],
                    tags=q.get("tags", []),
                    data_origin=q.get("data_origin", "synthetic"),
                )
                self.conn.add(item)
            self.conn.commit()
            return

        self.conn.execute(
            """
            INSERT INTO questions (id, level, skill_area, difficulty, text, options, answer, explanation, tags, data_origin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                level=excluded.level,
                skill_area=excluded.skill_area,
                difficulty=excluded.difficulty,
                text=excluded.text,
                options=excluded.options,
                answer=excluded.answer,
                explanation=excluded.explanation,
                tags=excluded.tags,
                data_origin=excluded.data_origin
            """,
            (
                q["id"],
                int(q["level"]),
                q["skill_area"],
                int(q["difficulty"]),
                q["text"],
                json.dumps(q["options"]),
                q["answer"],
                q["explanation"],
                json.dumps(q.get("tags", [])),
                q.get("data_origin", "synthetic"),
            ),
        )
        self.conn.commit()

    def _hydrate_question(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["options"] = json.loads(d["options"]) if isinstance(d["options"], str) else d["options"]
        d["tags"] = json.loads(d["tags"]) if isinstance(d["tags"], str) else d["tags"]
        return d

    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        if self.is_orm:
            q = self.conn.get(Question, question_id)
            if not q:
                return None
            return {
                "id": q.id,
                "level": q.level,
                "skill_area": q.skill_area,
                "difficulty": q.difficulty,
                "text": q.text,
                "options": q.options,
                "answer": q.answer,
                "explanation": q.explanation,
                "tags": q.tags or [],
                "data_origin": q.data_origin,
            }

        row = self.conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        return self._hydrate_question(row) if row else None

    def list_questions(
        self,
        level: Optional[int] = None,
        skill_area: Optional[str] = None,
        difficulty: Optional[int] = None,
        exclude_ids: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        if self.is_orm:
            stmt = select(Question)
            if level is not None:
                stmt = stmt.where(Question.level == int(level))
            if skill_area is not None:
                stmt = stmt.where(Question.skill_area == skill_area)
            if difficulty is not None:
                stmt = stmt.where(Question.difficulty == int(difficulty))
            stmt = stmt.order_by(Question.id.asc())
            items = self.conn.scalars(stmt).all()
            out = [
                {
                    "id": q.id,
                    "level": q.level,
                    "skill_area": q.skill_area,
                    "difficulty": q.difficulty,
                    "text": q.text,
                    "options": q.options,
                    "answer": q.answer,
                    "explanation": q.explanation,
                    "tags": q.tags or [],
                    "data_origin": q.data_origin,
                }
                for q in items
            ]
            if exclude_ids:
                out = [x for x in out if x["id"] not in exclude_ids]
            return out

        clauses: List[str] = []
        params: List[Any] = []
        if level is not None:
            clauses.append("level = ?")
            params.append(int(level))
        if skill_area is not None:
            clauses.append("skill_area = ?")
            params.append(skill_area)
        if difficulty is not None:
            clauses.append("difficulty = ?")
            params.append(int(difficulty))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM questions {where} ORDER BY id ASC", tuple(params)
        ).fetchall()
        out = [self._hydrate_question(r) for r in rows]
        if exclude_ids:
            out = [q for q in out if q["id"] not in exclude_ids]
        return out

    # ---- Attempts ----

    def record_attempt(
        self,
        user_id: str,
        item_type: str,
        item_id: str,
        answer: str,
        confidence: int,
        correct: bool,
        context: str,
        created_at: Optional[str] = None,
    ) -> str:
        self.ensure_user(user_id)
        aid = f"att_{uuid.uuid4().hex[:16]}"
        if self.is_orm:
            c_dt = datetime.fromisoformat(created_at) if created_at else datetime.now(timezone.utc)
            att = Attempt(
                id=aid,
                user_id=user_id,
                item_type=item_type,
                item_id=item_id,
                answer=str(answer),
                confidence=int(confidence),
                correct=bool(correct),
                context=context,
                created_at=c_dt,
            )
            self.conn.add(att)
            self.conn.commit()
            return aid

        self.conn.execute(
            """
            INSERT INTO attempts (id, user_id, item_type, item_id, answer, confidence, correct, context, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                aid,
                user_id,
                item_type,
                item_id,
                str(answer),
                int(confidence),
                1 if correct else 0,
                context,
                created_at or utc_now_iso(),
            ),
        )
        self.conn.commit()
        return aid

    def list_seen_item_ids(self, user_id: str, item_type: str) -> Set[str]:
        if self.is_orm:
            stmt = select(Attempt.item_id).where(Attempt.user_id == user_id, Attempt.item_type == item_type).distinct()
            return set(self.conn.scalars(stmt).all())

        rows = self.conn.execute(
            "SELECT DISTINCT item_id FROM attempts WHERE user_id = ? AND item_type = ?",
            (user_id, item_type),
        ).fetchall()
        return {r["item_id"] for r in rows}

    def list_attempts(
        self,
        user_id: Optional[str] = None,
        context: Optional[str] = None,
        item_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self.is_orm:
            stmt = select(Attempt)
            if user_id is not None:
                stmt = stmt.where(Attempt.user_id == user_id)
            if context is not None:
                stmt = stmt.where(Attempt.context == context)
            if item_type is not None:
                stmt = stmt.where(Attempt.item_type == item_type)
            stmt = stmt.order_by(Attempt.created_at.asc(), Attempt.id.asc())
            atts = self.conn.scalars(stmt).all()
            return [
                {
                    "id": a.id,
                    "user_id": a.user_id,
                    "item_type": a.item_type,
                    "item_id": a.item_id,
                    "answer": a.answer,
                    "confidence": a.confidence,
                    "correct": bool(a.correct),
                    "context": a.context,
                    "created_at": a.created_at.isoformat() if hasattr(a.created_at, "isoformat") else str(a.created_at),
                }
                for a in atts
            ]

        clauses: List[str] = []
        params: List[Any] = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if context is not None:
            clauses.append("context = ?")
            params.append(context)
        if item_type is not None:
            clauses.append("item_type = ?")
            params.append(item_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM attempts {where} ORDER BY created_at ASC, id ASC",
            tuple(params),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["correct"] = bool(d["correct"])
            out.append(d)
        return out

    # ---- Lessons & Plans ----

    def upsert_lesson(self, lesson: Dict[str, Any]) -> None:
        if self.is_orm:
            existing = self.conn.get(Lesson, lesson["id"])
            if existing:
                existing.level = int(lesson["level"])
                existing.skill_area = lesson["skill_area"]
                existing.title = lesson["title"]
                existing.minutes = int(lesson["minutes"])
                existing.sections = lesson["sections"]
                existing.check_questions = lesson["check_questions"]
                existing.data_origin = lesson.get("data_origin", "synthetic")
            else:
                item = Lesson(
                    id=lesson["id"],
                    level=int(lesson["level"]),
                    skill_area=lesson["skill_area"],
                    title=lesson["title"],
                    minutes=int(lesson["minutes"]),
                    sections=lesson["sections"],
                    check_questions=lesson["check_questions"],
                    data_origin=lesson.get("data_origin", "synthetic"),
                )
                self.conn.add(item)
            self.conn.commit()
            return

        self.conn.execute(
            """
            INSERT INTO lessons (id, level, skill_area, title, minutes, sections, check_questions, data_origin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                level=excluded.level,
                skill_area=excluded.skill_area,
                title=excluded.title,
                minutes=excluded.minutes,
                sections=excluded.sections,
                check_questions=excluded.check_questions,
                data_origin=excluded.data_origin
            """,
            (
                lesson["id"],
                int(lesson["level"]),
                lesson["skill_area"],
                lesson["title"],
                int(lesson["minutes"]),
                json.dumps(lesson["sections"]),
                json.dumps(lesson["check_questions"]),
                lesson.get("data_origin", "synthetic"),
            ),
        )
        self.conn.commit()

    def _hydrate_lesson(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["sections"] = json.loads(d["sections"]) if isinstance(d["sections"], str) else d["sections"]
        d["check_questions"] = json.loads(d["check_questions"]) if isinstance(d["check_questions"], str) else d["check_questions"]
        return d

    def get_lesson(self, lesson_id: str) -> Optional[Dict[str, Any]]:
        if self.is_orm:
            l = self.conn.get(Lesson, lesson_id)
            if not l:
                return None
            return {
                "id": l.id,
                "level": l.level,
                "skill_area": l.skill_area,
                "title": l.title,
                "minutes": l.minutes,
                "sections": l.sections,
                "check_questions": l.check_questions,
                "data_origin": l.data_origin,
            }

        row = self.conn.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        return self._hydrate_lesson(row) if row else None

    def list_lessons(self, level: Optional[int] = None, skill_area: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.is_orm:
            stmt = select(Lesson)
            if level is not None:
                stmt = stmt.where(Lesson.level == int(level))
            if skill_area is not None:
                stmt = stmt.where(Lesson.skill_area == skill_area)
            stmt = stmt.order_by(Lesson.level.asc(), Lesson.id.asc())
            items = self.conn.scalars(stmt).all()
            return [
                {
                    "id": l.id,
                    "level": l.level,
                    "skill_area": l.skill_area,
                    "title": l.title,
                    "minutes": l.minutes,
                    "sections": l.sections,
                    "check_questions": l.check_questions,
                    "data_origin": l.data_origin,
                }
                for l in items
            ]

        clauses: List[str] = []
        params: List[Any] = []
        if level is not None:
            clauses.append("level = ?")
            params.append(int(level))
        if skill_area is not None:
            clauses.append("skill_area = ?")
            params.append(skill_area)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM lessons {where} ORDER BY level ASC, id ASC", tuple(params)
        ).fetchall()
        return [self._hydrate_lesson(r) for r in rows]

    def upsert_plan(self, user_id: str, level: int, lesson_ids: List[str], progress: Dict[str, str]) -> None:
        if self.is_orm:
            self.ensure_user(user_id, level=level)
            stmt = select(Plan).where(Plan.user_id == user_id)
            plan = self.conn.scalars(stmt).first()
            if plan:
                plan.level = int(level)
                plan.lesson_ids = lesson_ids
                plan.progress = progress
            else:
                plan = Plan(user_id=user_id, level=int(level), lesson_ids=lesson_ids, progress=progress)
                self.conn.add(plan)
            self.conn.commit()
            return

        self.ensure_user(user_id, level=level)
        now = utc_now_iso()
        self.conn.execute(
            """
            INSERT INTO plans (user_id, level, lesson_ids, progress, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                level=excluded.level,
                lesson_ids=excluded.lesson_ids,
                progress=excluded.progress,
                updated_at=excluded.updated_at
            """,
            (user_id, int(level), json.dumps(lesson_ids), json.dumps(progress), now),
        )
        self.conn.commit()

    def get_plan(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.is_orm:
            stmt = select(Plan).where(Plan.user_id == user_id)
            p = self.conn.scalars(stmt).first()
            if not p:
                return None
            return {
                "id": p.id,
                "user_id": p.user_id,
                "level": p.level,
                "lesson_ids": p.lesson_ids,
                "progress": p.progress,
                "updated_at": p.updated_at.isoformat() if hasattr(p.updated_at, "isoformat") else str(p.updated_at),
            }

        row = self.conn.execute("SELECT * FROM plans WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["lesson_ids"] = json.loads(d["lesson_ids"]) if isinstance(d["lesson_ids"], str) else d["lesson_ids"]
        d["progress"] = json.loads(d["progress"]) if isinstance(d["progress"], str) else d["progress"]
        return d

    # ---- Scenarios ----

    def upsert_scenario(self, sc: Dict[str, Any]) -> None:
        if self.is_orm:
            existing = self.conn.get(Scenario, sc["id"])
            as_of = date.fromisoformat(str(sc["as_of_date"])) if isinstance(sc["as_of_date"], str) else sc["as_of_date"]
            if existing:
                existing.symbol = sc["symbol"]
                existing.as_of_date = as_of
                existing.window_days = int(sc["window_days"])
                existing.context = sc["context"]
                existing.outcome = sc["outcome"]
                existing.explanation = sc["explanation"]
                existing.key_clues = sc.get("key_clues", [])
                existing.tags = sc.get("tags", [])
                existing.difficulty = int(sc["difficulty"])
                existing.data_origin = sc["data_origin"]
            else:
                item = Scenario(
                    id=sc["id"],
                    symbol=sc["symbol"],
                    as_of_date=as_of,
                    window_days=int(sc["window_days"]),
                    context=sc["context"],
                    outcome=sc["outcome"],
                    explanation=sc["explanation"],
                    key_clues=sc.get("key_clues", []),
                    tags=sc.get("tags", []),
                    difficulty=int(sc["difficulty"]),
                    data_origin=sc["data_origin"],
                )
                self.conn.add(item)
            self.conn.commit()
            return

        self.conn.execute(
            """
            INSERT INTO scenarios (id, symbol, as_of_date, window_days, context, outcome, explanation, key_clues, tags, difficulty, data_origin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                symbol=excluded.symbol,
                as_of_date=excluded.as_of_date,
                window_days=excluded.window_days,
                context=excluded.context,
                outcome=excluded.outcome,
                explanation=excluded.explanation,
                key_clues=excluded.key_clues,
                tags=excluded.tags,
                difficulty=excluded.difficulty,
                data_origin=excluded.data_origin
            """,
            (
                sc["id"],
                sc["symbol"],
                str(sc["as_of_date"]),
                int(sc["window_days"]),
                json.dumps(sc["context"]),
                json.dumps(sc["outcome"]),
                sc["explanation"],
                json.dumps(sc.get("key_clues", [])),
                json.dumps(sc.get("tags", [])),
                int(sc["difficulty"]),
                sc["data_origin"],
            ),
        )
        self.conn.commit()

    def _hydrate_scenario(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["context"] = json.loads(d["context"]) if isinstance(d["context"], str) else d["context"]
        d["outcome"] = json.loads(d["outcome"]) if isinstance(d["outcome"], str) else d["outcome"]
        d["key_clues"] = json.loads(d["key_clues"]) if isinstance(d["key_clues"], str) else d["key_clues"]
        d["tags"] = json.loads(d["tags"]) if isinstance(d["tags"], str) else d["tags"]
        return d

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        if self.is_orm:
            s = self.conn.get(Scenario, scenario_id)
            if not s:
                return None
            return {
                "id": s.id,
                "symbol": s.symbol,
                "as_of_date": s.as_of_date.isoformat() if hasattr(s.as_of_date, "isoformat") else str(s.as_of_date),
                "window_days": s.window_days,
                "context": s.context,
                "outcome": s.outcome,
                "explanation": s.explanation,
                "key_clues": s.key_clues or [],
                "tags": s.tags or [],
                "difficulty": s.difficulty,
                "data_origin": s.data_origin,
            }

        row = self.conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
        return self._hydrate_scenario(row) if row else None

    def list_scenarios(
        self,
        difficulty: Optional[int] = None,
        exclude_ids: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        if self.is_orm:
            stmt = select(Scenario)
            if difficulty is not None:
                stmt = stmt.where(Scenario.difficulty == int(difficulty))
            stmt = stmt.order_by(Scenario.id.asc())
            items = self.conn.scalars(stmt).all()
            out = [
                {
                    "id": s.id,
                    "symbol": s.symbol,
                    "as_of_date": s.as_of_date.isoformat() if hasattr(s.as_of_date, "isoformat") else str(s.as_of_date),
                    "window_days": s.window_days,
                    "context": s.context,
                    "outcome": s.outcome,
                    "explanation": s.explanation,
                    "key_clues": s.key_clues or [],
                    "tags": s.tags or [],
                    "difficulty": s.difficulty,
                    "data_origin": s.data_origin,
                }
                for s in items
            ]
            if exclude_ids:
                out = [x for x in out if x["id"] not in exclude_ids]
            return out

        if difficulty is not None:
            rows = self.conn.execute(
                "SELECT * FROM scenarios WHERE difficulty = ? ORDER BY id ASC",
                (int(difficulty),),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM scenarios ORDER BY id ASC").fetchall()
        out = [self._hydrate_scenario(r) for r in rows]
        if exclude_ids:
            out = [s for s in out if s["id"] not in exclude_ids]
        return out

    # ---- Sessions (Onboarding / Assessment / Study) ----

    def create_session(
        self,
        session_id: str,
        user_id: str,
        session_type: str,
        state: Dict[str, Any],
        target_level: Optional[int] = None,
    ) -> None:
        self.ensure_user(user_id)
        if self.is_orm:
            sess = EduSession(
                id=session_id,
                user_id=user_id,
                session_type=session_type,
                target_level=target_level,
                state=state,
                completed=False,
            )
            self.conn.add(sess)
            self.conn.commit()
            return

        self.conn.execute(
            """
            INSERT INTO edu_sessions (id, user_id, session_type, target_level, state, completed, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (session_id, user_id, session_type, target_level, json.dumps(state), utc_now_iso()),
        )
        self.conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if self.is_orm:
            sess = self.conn.get(EduSession, session_id)
            if not sess:
                return None
            return {
                "id": sess.id,
                "user_id": sess.user_id,
                "session_type": sess.session_type,
                "target_level": sess.target_level,
                "state": sess.state,
                "completed": bool(sess.completed),
                "created_at": sess.created_at.isoformat() if hasattr(sess.created_at, "isoformat") else str(sess.created_at),
            }

        row = self.conn.execute("SELECT * FROM edu_sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["state"] = json.loads(d["state"]) if isinstance(d["state"], str) else d["state"]
        d["completed"] = bool(d["completed"])
        return d

    def update_session(self, session_id: str, state: Dict[str, Any], completed: bool = False) -> None:
        if self.is_orm:
            sess = self.conn.get(EduSession, session_id)
            if sess:
                sess.state = state
                sess.completed = bool(completed)
                self.conn.commit()
            return

        self.conn.execute(
            "UPDATE edu_sessions SET state = ?, completed = ? WHERE id = ?",
            (json.dumps(state), 1 if completed else 0, session_id),
        )
        self.conn.commit()

    # ---- Explain a Stock Cache ----

    def upsert_explain(self, rec: Dict[str, Any]) -> None:
        if self.is_orm:
            stmt = select(ExplainCache).where(
                ExplainCache.symbol == rec["symbol"].upper(),
                ExplainCache.year == int(rec["year"]),
            )
            existing = self.conn.scalars(stmt).first()
            if existing:
                existing.chart = rec["chart"]
                existing.moves = rec["moves"]
                existing.summary = rec["summary"]
                existing.data_origin = rec["data_origin"]
            else:
                item = ExplainCache(
                    symbol=rec["symbol"].upper(),
                    year=int(rec["year"]),
                    chart=rec["chart"],
                    moves=rec["moves"],
                    summary=rec["summary"],
                    data_origin=rec["data_origin"],
                )
                self.conn.add(item)
            self.conn.commit()
            return

        self.conn.execute(
            """
            INSERT INTO edu_explain_cache (symbol, year, chart, moves, summary, data_origin)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, year) DO UPDATE SET
                chart=excluded.chart,
                moves=excluded.moves,
                summary=excluded.summary,
                data_origin=excluded.data_origin
            """,
            (
                rec["symbol"].upper(),
                int(rec["year"]),
                json.dumps(rec["chart"]),
                json.dumps(rec["moves"]),
                rec["summary"],
                rec["data_origin"],
            ),
        )
        self.conn.commit()

    def get_explain(self, symbol: str, year: int) -> Optional[Dict[str, Any]]:
        if self.is_orm:
            stmt = select(ExplainCache).where(
                ExplainCache.symbol == symbol.upper(),
                ExplainCache.year == int(year),
            )
            item = self.conn.scalars(stmt).first()
            if not item:
                return None
            return {
                "symbol": item.symbol,
                "year": item.year,
                "chart": item.chart,
                "moves": item.moves,
                "summary": item.summary,
                "data_origin": item.data_origin,
            }

        row = self.conn.execute(
            "SELECT * FROM edu_explain_cache WHERE symbol = ? AND year = ?",
            (symbol.upper(), int(year)),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["chart"] = json.loads(d["chart"]) if isinstance(d["chart"], str) else d["chart"]
        d["moves"] = json.loads(d["moves"]) if isinstance(d["moves"], str) else d["moves"]
        return d

    def list_explain_records(self) -> List[Dict[str, Any]]:
        if self.is_orm:
            stmt = select(
                ExplainCache.symbol,
                ExplainCache.year,
                ExplainCache.data_origin,
            ).order_by(ExplainCache.symbol.asc(), ExplainCache.year.asc())
            rows = self.conn.execute(stmt).all()
            return [{"symbol": r[0], "year": r[1], "data_origin": r[2]} for r in rows]

        rows = self.conn.execute(
            "SELECT symbol, year, data_origin FROM edu_explain_cache ORDER BY symbol ASC, year ASC"
        ).fetchall()
        return [dict(r) for r in rows]
