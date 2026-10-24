from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from visionguard.db.base import Base, Identity, Updated
from visionguard.db.enums import JobState


class InferenceJob(Identity, Updated, Base):
    __tablename__ = "inference_jobs"
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 255", name="idempotency_key_length"
        ),
        CheckConstraint(
            "state <> 'FAILED' OR error_code IS NOT NULL", name="failed_error_code"
        ),
        CheckConstraint(
            "(finished_at IS NOT NULL) = (state IN ('SUCCEEDED','FAILED'))",
            name="finished_state",
        ),
        Index("ix_inference_jobs_state_created_at", "state", "created_at"),
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT")
    )
    state: Mapped[JobState] = mapped_column(
        Enum(JobState, name="job_state"),
        default=JobState.QUEUED,
        server_default="QUEUED",
    )
    attempt_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    celery_task_id: Mapped[str | None]
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
