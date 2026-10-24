"""initial_schema"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "media_assets",
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column(
            "validation_status",
            sa.Enum("PENDING", "VALID", "INVALID", name="validation_status"),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "mime_type IN ('image/jpeg','image/png','image/webp')",
            name=op.f("ck_media_assets_mime_type"),
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_media_assets_sha256_hex")
        ),
        sa.CheckConstraint("height > 0", name=op.f("ck_media_assets_height_positive")),
        sa.CheckConstraint(
            "size_bytes > 0", name=op.f("ck_media_assets_size_bytes_positive")
        ),
        sa.CheckConstraint("width > 0", name=op.f("ck_media_assets_width_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_assets")),
        sa.UniqueConstraint("object_key", name=op.f("uq_media_assets_object_key")),
    )
    op.create_index(
        op.f("ix_media_assets_sha256"), "media_assets", ["sha256"], unique=False
    )
    op.create_table(
        "model_versions",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("artifact_uri", sa.String(), nullable=True),
        sa.Column("artifact_checksum", sa.String(), nullable=True),
        sa.Column("label_schema_version", sa.String(), nullable=False),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(labels) = 'array' AND labels <> '[]'::jsonb "
            "AND NOT jsonb_path_exists(labels, "
            "'$[*] ? (@.type() != \"string\")')",
            name=op.f("ck_model_versions_labels_strings"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_versions")),
        sa.UniqueConstraint("name", "version", name="uq_model_versions_name_version"),
    )
    op.create_index(
        "uq_model_versions_active_name",
        "model_versions",
        ["name"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "inference_jobs",
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "QUEUED", "RUNNING", "RETRYING", "SUCCEEDED", "FAILED", name="job_state"
            ),
            server_default="QUEUED",
            nullable=False,
        ),
        sa.Column(
            "attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("celery_task_id", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(finished_at IS NOT NULL) = (state IN ('SUCCEEDED','FAILED'))",
            name=op.f("ck_inference_jobs_finished_state"),
        ),
        sa.CheckConstraint(
            "state <> 'FAILED' OR error_code IS NOT NULL",
            name=op.f("ck_inference_jobs_failed_error_code"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_inference_jobs_attempt_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 255",
            name=op.f("ck_inference_jobs_idempotency_key_length"),
        ),
        sa.ForeignKeyConstraint(
            ["media_asset_id"],
            ["media_assets.id"],
            name=op.f("fk_inference_jobs_media_asset_id_media_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name=op.f("fk_inference_jobs_model_version_id_model_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inference_jobs")),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_inference_jobs_idempotency_key")
        ),
    )
    op.create_index(
        op.f("ix_inference_jobs_media_asset_id"),
        "inference_jobs",
        ["media_asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_inference_jobs_state_created_at",
        "inference_jobs",
        ["state", "created_at"],
        unique=False,
    )
    op.create_table(
        "predictions",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "label_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "thresholds", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("decisions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("latency_ms", sa.Double(), nullable=False),
        sa.Column("preprocessing_version", sa.String(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(decisions) = 'object'",
            name=op.f("ck_predictions_decisions_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(label_scores) = 'object'",
            name=op.f("ck_predictions_label_scores_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(thresholds) = 'object'",
            name=op.f("ck_predictions_thresholds_object"),
        ),
        sa.CheckConstraint(
            "latency_ms >= 0", name=op.f("ck_predictions_latency_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["inference_jobs.id"],
            name=op.f("fk_predictions_job_id_inference_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name=op.f("fk_predictions_model_version_id_model_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_predictions")),
        sa.UniqueConstraint("job_id", name=op.f("uq_predictions_job_id")),
    )


def downgrade():
    op.drop_table("predictions")
    op.drop_index("ix_inference_jobs_state_created_at", table_name="inference_jobs")
    op.drop_index(op.f("ix_inference_jobs_media_asset_id"), table_name="inference_jobs")
    op.drop_table("inference_jobs")
    op.drop_index(
        "uq_model_versions_active_name",
        table_name="model_versions",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_table("model_versions")
    op.drop_index(op.f("ix_media_assets_sha256"), table_name="media_assets")
    op.drop_table("media_assets")
    sa.Enum(name="job_state").drop(op.get_bind())
    sa.Enum(name="validation_status").drop(op.get_bind())
