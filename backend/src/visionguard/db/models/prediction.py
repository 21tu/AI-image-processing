from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from visionguard.db.base import Base, Identity


class Prediction(Identity, Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(label_scores) = 'object'", name="label_scores_object"
        ),
        CheckConstraint(
            "jsonb_typeof(thresholds) = 'object'", name="thresholds_object"
        ),
        CheckConstraint("jsonb_typeof(decisions) = 'object'", name="decisions_object"),
        CheckConstraint(
            "latency_ms >= 0 AND latency_ms <> 'NaN'::float8 "
            "AND latency_ms < 'Infinity'::float8",
            name="latency_nonnegative",
        ),
    )
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("inference_jobs.id", ondelete="RESTRICT"), unique=True
    )
    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT")
    )
    label_scores: Mapped[dict[str, float]] = mapped_column(JSONB)
    thresholds: Mapped[dict[str, float]] = mapped_column(JSONB)
    decisions: Mapped[dict[str, bool]] = mapped_column(JSONB)
    latency_ms: Mapped[float]
    preprocessing_version: Mapped[str]
