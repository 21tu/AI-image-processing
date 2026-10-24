from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint, false, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from visionguard.db.base import Base, Identity


class ModelVersion(Identity, Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_model_versions_name_version"),
        Index(
            "uq_model_versions_active_name",
            "name",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        CheckConstraint(
            "jsonb_typeof(labels) = 'array' AND labels <> '[]'::jsonb "
            "AND NOT jsonb_path_exists(labels, "
            "'$[*] ? (@.type() != \"string\")')",
            name="labels_strings",
        ),
    )
    name: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)
    artifact_uri: Mapped[str | None]
    artifact_checksum: Mapped[str | None]
    label_schema_version: Mapped[str]
    labels: Mapped[list[str]] = mapped_column(JSONB)
    is_demo: Mapped[bool] = mapped_column(server_default=false(), default=False)
    is_active: Mapped[bool] = mapped_column(server_default=false(), default=False)
