from importlib.util import module_from_spec, spec_from_file_location
from os import getenv
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.verifier.models import Source
from app.verifier.schemas import VerifyRequest


def test_verifier_revision_upgrades_downgrades_and_enforces_origin():
    path = next(
        (Path(__file__).resolve().parents[3] / "db/migrations/versions").glob(
            "*_verifier_tables.py"
        )
    )
    spec = spec_from_file_location("verifier_revision", path)
    assert spec and spec.loader
    revision = module_from_spec(spec)
    spec.loader.exec_module(revision)
    engine = create_engine(getenv("VERIFIER_TEST_DATABASE_URL", "sqlite://"))
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            revision.upgrade()
        assert set(inspect(connection).get_table_names()) == {
            "sources",
            "submissions",
            "claims",
            "source_rating_history",
        }
    with Session(engine) as session:
        values = {
            "platform": "telegram",
            "handle": "public-source",
            "score": 60,
            "scored_claims": 5,
            "label": "semi_reliable",
        }
        session.add(Source(id=uuid4(), **values, data_origin="real"))
        session.commit()
        session.add(Source(id=uuid4(), **values, data_origin="unknown"))
        with pytest.raises(IntegrityError, match="ck_sources_origin"):
            session.flush()
        session.rollback()
        session.add(Source(id=uuid4(), **values, data_origin="real"))
        with pytest.raises(IntegrityError):
            session.flush()
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            revision.downgrade()
            assert not inspect(connection).get_table_names()
            revision.upgrade()
        assert "claims" in inspect(connection).get_table_names()
        with Operations.context(MigrationContext.configure(connection)):
            revision.downgrade()
    engine.dispose()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"text": "  "},
        {"url": "https://t.me/s/test/1", "text": "tip"},
        {"text": "tip", "user_confidence": 49},
        {"text": "tip", "data_origin": "synthetic"},
    ],
)
def test_verify_rejects_invalid_or_ambiguous_requests(body):
    with pytest.raises(ValidationError):
        VerifyRequest.model_validate(body)


def test_verify_accepts_a_tip_and_optional_source_guess():
    req = VerifyRequest(
        text="  An example tip.  ", user_guess="not_reliable", user_confidence=80
    )
    assert req.text == "An example tip."
    assert req.user_guess == "not_reliable"
