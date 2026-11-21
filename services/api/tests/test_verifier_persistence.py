"""Owner/TTL/restart and migration checks, also runnable on isolated Postgres."""

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import User
from app.core.errors import AppError, NotFoundError
from app.core.models import UserRecord
from app.nasdaq_verifier import service
from app.nasdaq_verifier.gate import GateInputs, missing_requirements, read_gate_inputs
from app.nasdaq_verifier.models import NasdaqChallenge
from app.verifier.models import Source, Submission


def migrate(db: Session, revision: str, *, downgrade: bool = False) -> None:
    cfg = Config(str(Path(__file__).resolve().parents[3] / "db/alembic.ini"))
    cfg.attributes["connection"] = db.connection()
    (command.downgrade if downgrade else command.upgrade)(cfg, revision)
    db.commit()


@pytest.fixture(params=["sqlite", "postgres"])
def persistence_engine(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[Engine]:
    """Never migrate the configured application's schema: use a fresh private schema."""
    if request.param == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'persistence.db'}")

        @event.listens_for(engine, "connect")
        def sqlite_fk(conn, record):
            conn.execute("PRAGMA foreign_keys=ON")

        with Session(engine) as db:
            migrate(db, "head")
        yield engine
        engine.dispose()
        return
    url = os.getenv("VERIFIER_POSTGRES_TEST_URL")
    if not url:
        pytest.skip(
            "Set VERIFIER_POSTGRES_TEST_URL for isolated-schema Postgres checks"
        )
    # Managed Postgres may close an idle admin connection while the test runs.
    # Check it before cleanup; do not suppress a failed assertion or DROP.
    admin = create_engine(url, pool_pre_ping=True)
    schema = "verifier_acceptance_" + uuid4().hex
    assert (
        schema.startswith("verifier_acceptance_") and schema.replace("_", "").isalnum()
    )
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def search_path(conn, record):
        with conn.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}"')
        conn.commit()

    try:
        with Session(engine) as db:
            migrate(db, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def owner(db: Session) -> str:
    uid = str(uuid4())
    db.add(UserRecord(id=uid, current_level=4))
    db.commit()
    return uid


def questions():
    return [
        {"id": f"q{i}", "text": "Read a figure", "options": ["1", "2"], "_answer": "1"}
        for i in range(1, 4)
    ]


def answers():
    return [
        {"question_id": f"q{i}", "answer": "1", "confidence": 90} for i in range(1, 4)
    ]


def test_key_survives_connections_and_rejects_wrong_owner_and_replay(
    persistence_engine,
):
    with Session(persistence_engine) as db:
        uid = owner(db)
        other = owner(db)
        cid, public = service.issue(db, uid, questions())
        assert all("_answer" not in q for q in public)
    persistence_engine.dispose()  # Discard the issuing instance's entire connection pool.
    with Session(persistence_engine) as db:
        with pytest.raises(NotFoundError):
            service.submit(db, cid, other, answers())
        db.rollback()
        assert db.get(NasdaqChallenge, cid) is not None
        result = service.submit(db, cid, uid, answers())
        assert result["passed"] and result["score"] == 1
    with Session(persistence_engine) as db, pytest.raises(NotFoundError):
        service.submit(db, cid, uid, answers())


def test_fresh_process_consumes_persisted_key(persistence_engine):
    with Session(persistence_engine) as db:
        uid = owner(db)
        cid, _ = service.issue(db, uid, questions())
        schema = (
            db.scalar(text("SELECT current_schema()"))
            if persistence_engine.dialect.name == "postgresql"
            else ""
        )
    child_env = os.environ.copy()
    child_env["VERIFIER_RESTART_DB"] = persistence_engine.url.render_as_string(
        hide_password=False
    )
    child_env["VERIFIER_RESTART_SCHEMA"] = schema
    child_env["VERIFIER_RESTART_OWNER"] = uid
    child_env["VERIFIER_RESTART_KEY"] = cid
    script = """
import json, os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from app.core.models import UserRecord
from app.nasdaq_verifier.service import submit
engine = create_engine(os.environ["VERIFIER_RESTART_DB"])
schema = os.environ["VERIFIER_RESTART_SCHEMA"]
if schema:
    assert schema.startswith("verifier_acceptance_") and schema.replace("_", "").isalnum()
    @event.listens_for(engine, "connect")
    def search_path(conn, record):
        with conn.cursor() as c:
            c.execute('SET search_path TO "' + schema + '"')
        conn.commit()
with Session(engine) as db:
    result = submit(db, os.environ["VERIFIER_RESTART_KEY"], os.environ["VERIFIER_RESTART_OWNER"],
                    [{"question_id": "q" + str(i), "answer": "1", "confidence": 90}
                     for i in range(1, 4)])
    print(json.dumps({"score": result["score"], "passed": result["passed"]}))
engine.dispose()
"""
    child = subprocess.run(
        [sys.executable, "-c", script],
        env=child_env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout) == {"score": 1.0, "passed": True}


def test_concurrent_submits_have_one_winner(persistence_engine):
    with Session(persistence_engine) as db:
        uid = owner(db)
        cid, _ = service.issue(db, uid, questions())

    def consume(_):
        with Session(persistence_engine) as db:
            try:
                service.submit(db, cid, uid, answers())
                return "scored"
            except NotFoundError:
                return "not_found"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(consume, range(2))) == ["not_found", "scored"]


def test_expired_and_malformed_submissions_fail_closed(persistence_engine):
    with Session(persistence_engine) as db:
        uid = owner(db)
        cid, _ = service.issue(db, uid, questions())
        for bad in (
            [],
            answers()[:2],
            [answers()[0]] * 3,
            [{**a, "question_id": "unknown"} for a in answers()],
        ):
            with pytest.raises(AppError, match="exactly once"):
                service.submit(db, cid, uid, bad)
            assert db.get(NasdaqChallenge, cid) is not None
        ch = db.get_one(NasdaqChallenge, cid)
        ch.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        with pytest.raises(NotFoundError):
            service.submit(db, cid, uid, answers())
        db.rollback()
        service.issue(db, uid, questions())
        assert db.get(NasdaqChallenge, cid) is None


def test_migrations_down_up_preserve_submissions_and_enforce_owner(persistence_engine):
    with Session(persistence_engine) as db:
        uid = owner(db)
        source = Source(platform="test", handle="fixture", data_origin="synthetic")
        db.add(source)
        db.flush()
        submission = Submission(
            user_id=UUID(uid),
            source_id=source.id,
            raw_content="fixture",
            content_hash="a" * 64,
            captured_at=datetime.now(UTC),
            data_origin="synthetic",
        )
        db.add(submission)
        db.commit()
        sid = submission.id
        migrate(db, "20261120_01_edu", downgrade=True)
        # The old schema has no transcript column; verify retention by its stable key.
        assert db.scalar(select(Submission.id).where(Submission.id == sid)) == sid
        assert not inspect(db.connection()).has_table("nasdaq_challenges")
        migrate(db, "head")
        assert db.get(Submission, sid) is not None
        fks = inspect(db.connection()).get_foreign_keys("submissions")
        assert any(fk["name"] == "fk_submissions_user_id_users" for fk in fks)
        submission.user_id = uuid4()
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert str(db.get_one(Submission, sid).user_id) == uid


@pytest.mark.parametrize(
    "progress,brier",
    [
        (None, None),
        (99.9, 0.2),
        (101, 0.2),
        (float("nan"), 0.2),
        (100, float("nan")),
        (100, -1),
        (100, float("inf")),
        (100, 0.25001),
    ],
)
def test_invalid_gate_inputs_are_locked(progress, brier):
    assert missing_requirements(
        User(id=str(uuid4()), level=4), GateInputs(progress, brier)
    )


def test_real_plan_json_and_latest_calibration(persistence_engine):
    with Session(persistence_engine) as db:
        uid = owner(db)
        # Use typed owner binds on both database backends.
        from app.education.models import Plan, SkillScore

        db.add(
            Plan(
                user_id=uid,
                level=4,
                lesson_ids=["a", "b"],
                progress={"a": "completed", "b": "in_progress"},
            )
        )
        db.add(SkillScore(user_id=uid, skill_area="basics", score=80, brier=0.1))
        db.commit()
        user = User(id=uid, level=4)
        assert read_gate_inputs(db, user).progress_pct == 50
        plan = db.scalar(select(Plan).where(Plan.user_id == uid))
        plan.progress = {"a": "completed", "b": "completed"}
        db.commit()
        assert not missing_requirements(user, read_gate_inputs(db, user))
        db.add(
            SkillScore(
                user_id=uid,
                skill_area="basics",
                score=40,
                brier=0.4,
                measured_at=datetime.now(UTC) + timedelta(seconds=1),
            )
        )
        db.commit()
        assert "brier_lte_0.25" in missing_requirements(
            user, read_gate_inputs(db, user)
        )
