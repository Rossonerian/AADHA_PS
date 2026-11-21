from importlib.util import module_from_spec, spec_from_file_location
from os import getenv
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import MetaData, Table, create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    # Exercise this historical revision with its reflected schema, not future ORM columns.
    legacy_source = Table("sources", MetaData(), autoload_with=engine)
    with Session(engine) as session:
        values = {
            "platform": "telegram",
            "handle": "public-source",
            "score": 60,
            "scored_claims": 5,
            "label": "semi_reliable",
        }
        session.execute(
            legacy_source.insert().values(id=uuid4().hex, **values, data_origin="real")
        )
        session.commit()
        with pytest.raises(IntegrityError, match="ck_sources_origin"):
            session.execute(
                legacy_source.insert().values(
                    id=uuid4().hex, **values, data_origin="unknown"
                )
            )
        session.rollback()
        with pytest.raises(IntegrityError):
            session.execute(
                legacy_source.insert().values(
                    id=uuid4().hex, **values, data_origin="real"
                )
            )
        session.rollback()
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
        {"image_base64": "image", "text": "tip"},
        {"image_base64": "image", "url": "https://x.com/test/status/1"},
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


def test_verify_accepts_pasted_text_with_a_context_link():
    req = VerifyRequest(
        text="JBM Auto 489 sl 480 intraday", url="https://x.com/StocksResearch/status/1"
    )
    assert req.text == "JBM Auto 489 sl 480 intraday"
    assert req.url == "https://x.com/StocksResearch/status/1"
