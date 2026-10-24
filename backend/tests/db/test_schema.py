import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def database():
    if os.getenv("SKIP_DB_TESTS") == "1":
        pytest.skip("SKIP_DB_TESTS=1")
    url = make_url(
        os.getenv(
            "TEST_DATABASE_URL",
            "postgresql+psycopg://visionguard:local-dev-only@127.0.0.1:5432/visionguard_test",
        )
    )
    if url.database != "visionguard_test":
        pytest.fail("TEST_DATABASE_URL must target dedicated visionguard_test database")
    admin = create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},
    )
    try:
        with admin.connect() as conn:
            if not conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname='visionguard_test'")
            ):
                conn.execute(text("CREATE DATABASE visionguard_test"))
    except Exception as exc:
        pytest.fail(
            "PostgreSQL unavailable or test database creation failed: "
            f"{type(exc).__name__}"
        )
    finally:
        admin.dispose()
    from alembic.config import Config

    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.attributes["database_url"] = url.render_as_string(hide_password=False)
    from alembic import command

    engine = create_engine(url)
    command.upgrade(config, "head")
    yield engine, config
    engine.dispose()


def test_migrations_and_parity(database):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from alembic import command
    from visionguard.db import models  # noqa: F401
    from visionguard.db.base import Base

    engine, config = database
    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) == {
        "alembic_version",
        "media_assets",
        "model_versions",
        "inference_jobs",
        "predictions",
    }
    with engine.connect() as conn:
        assert (
            compare_metadata(
                MigrationContext.configure(
                    conn, opts={"compare_type": True, "compare_server_default": True}
                ),
                Base.metadata,
            )
            == []
        )
    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    command.upgrade(config, "head")


@pytest.fixture
def chain(database):
    from visionguard.db.models import InferenceJob, MediaAsset, ModelVersion, Prediction

    engine, _ = database
    with engine.connect() as conn:
        transaction = conn.begin()
        with Session(conn, join_transaction_mode="create_savepoint") as session:
            media = MediaAsset(
                object_key="image",
                sha256="a" * 64,
                mime_type="image/png",
                size_bytes=1,
                width=1,
                height=1,
                validation_status="VALID",
            )
            model = ModelVersion(
                name="demo",
                version="1",
                labels=["adult"],
                label_schema_version="1",
                is_demo=True,
                is_active=True,
            )
            session.add_all([media, model])
            session.flush()
            job = InferenceJob(
                media_asset_id=media.id,
                model_version_id=model.id,
                idempotency_key="key",
            )
            session.add(job)
            session.flush()
            prediction = Prediction(
                job_id=job.id,
                model_version_id=model.id,
                label_scores={"adult": 0.1},
                thresholds={"adult": 0.5},
                decisions={"adult": False},
                latency_ms=0.1,
                preprocessing_version="1",
            )
            session.add(prediction)
            session.flush()
            yield session, media, model, job, prediction
        transaction.rollback()


def test_round_trip(chain):
    session, media, model, job, prediction = chain
    session.expire_all()
    assert prediction.job_id == job.id
    assert job.state == "QUEUED"
    assert job.attempt_count == 0
    assert media.created_at.tzinfo is not None
    assert model.labels == ["adult"]


@pytest.mark.parametrize(
    "table,column,value",
    [
        ("media_assets", "sha256", "'A'"),
        ("media_assets", "mime_type", "'text/plain'"),
        ("media_assets", "size_bytes", "0"),
        ("media_assets", "width", "0"),
        ("media_assets", "height", "0"),
        ("media_assets", "validation_status", "'UNKNOWN'"),
        ("model_versions", "labels", "'[]'::jsonb"),
        ("model_versions", "labels", "'{}'::jsonb"),
        ("model_versions", "labels", "'[1]'::jsonb"),
        ("inference_jobs", "attempt_count", "-1"),
        ("inference_jobs", "idempotency_key", "''"),
        ("inference_jobs", "idempotency_key", "repeat('a',256)"),
        ("inference_jobs", "state", "'FAILED'"),
        ("inference_jobs", "state", "'SUCCEEDED'"),
        ("inference_jobs", "state", "'UNKNOWN'"),
        ("inference_jobs", "finished_at", "now()"),
        ("inference_jobs", "media_asset_id", "'00000000-0000-0000-0000-000000000000'"),
        (
            "inference_jobs",
            "model_version_id",
            "'00000000-0000-0000-0000-000000000000'",
        ),
        ("predictions", "job_id", "'00000000-0000-0000-0000-000000000000'"),
        ("predictions", "model_version_id", "'00000000-0000-0000-0000-000000000000'"),
        ("predictions", "latency_ms", "-1"),
        ("predictions", "latency_ms", "'NaN'::float8"),
        ("predictions", "latency_ms", "'Infinity'::float8"),
        ("predictions", "latency_ms", "'-Infinity'::float8"),
        ("predictions", "label_scores", "'[]'::jsonb"),
        ("predictions", "thresholds", "'[]'::jsonb"),
        ("predictions", "decisions", "'[]'::jsonb"),
    ],
)
def test_checks_and_foreign_keys(chain, table, column, value):
    session, *_ = chain
    with (
        pytest.raises(DataError if value == "'UNKNOWN'" else IntegrityError),
        session.begin_nested(),
    ):
        session.execute(text(f"UPDATE {table} SET {column} = {value}"))


@pytest.mark.parametrize(
    "table,changes",
    [
        ("media_assets", ""),
        ("model_versions", ""),
        ("model_versions", "version"),
        ("inference_jobs", ""),
        ("predictions", ""),
    ],
)
def test_uniqueness(chain, table, changes):
    session, *_ = chain
    columns = [
        c["name"]
        for c in inspect(session.connection()).get_columns(table)
        if c["name"] != "id"
    ]
    expressions = ["'2'" if c == changes else c for c in columns]
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(
            text(
                f"INSERT INTO {table} (id, {', '.join(columns)}) "
                f"SELECT gen_random_uuid(), {', '.join(expressions)} FROM {table}"
            )
        )


@pytest.mark.parametrize("table", ["media_assets", "model_versions", "inference_jobs"])
def test_restrict_delete(chain, table):
    session, *_ = chain
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(text(f"DELETE FROM {table}"))


def test_failed_requires_error_code_with_finished_timestamp(chain):
    session, *_ = chain
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(
            text("UPDATE inference_jobs SET state='FAILED', finished_at=now()")
        )


def test_successful_and_failed_terminal_states(chain):
    session, _, _, job, _ = chain
    session.execute(
        text("UPDATE inference_jobs SET state='SUCCEEDED', finished_at=now()")
    )
    session.expire_all()
    assert job.finished_at is not None
    session.execute(
        text(
            "UPDATE inference_jobs SET state='FAILED', "
            "error_code='demo', finished_at=now()"
        )
    )
    session.expire_all()
    assert job.error_code == "demo"


def test_same_hash_and_inactive_versions_allowed(chain):
    from visionguard.db.models import MediaAsset, ModelVersion

    session, media, model, *_ = chain
    session.add(
        MediaAsset(
            object_key="another",
            sha256=media.sha256,
            mime_type=media.mime_type,
            size_bytes=1,
            width=1,
            height=1,
        )
    )
    session.add(
        ModelVersion(
            name=model.name, version="2", labels=["adult"], label_schema_version="1"
        )
    )
    session.flush()


def test_named_schema_objects(database):
    from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

    from visionguard.db.base import Base

    engine, _ = database
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        assert inspector.get_pk_constraint(table.name)["name"] == table.primary_key.name
        for kind, getter in [
            (CheckConstraint, inspector.get_check_constraints),
            (ForeignKeyConstraint, inspector.get_foreign_keys),
            (UniqueConstraint, inspector.get_unique_constraints),
        ]:
            assert {c.name for c in table.constraints if isinstance(c, kind)} == {
                c["name"] for c in getter(table.name)
            }
        assert {i.name for i in table.indexes} == {
            i["name"]
            for i in inspector.get_indexes(table.name)
            if not i.get("duplicates_constraint")
        }
