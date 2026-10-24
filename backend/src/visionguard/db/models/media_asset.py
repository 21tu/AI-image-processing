from sqlalchemy import CHAR, CheckConstraint, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from visionguard.db.base import Base, Identity, Updated
from visionguard.db.enums import ValidationStatus


class MediaAsset(Identity, Updated, Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint(
            "mime_type IN ('image/jpeg','image/png','image/webp')", name="mime_type"
        ),
        CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
        CheckConstraint("width > 0", name="width_positive"),
        CheckConstraint("height > 0", name="height_positive"),
    )
    object_key: Mapped[str] = mapped_column(String, unique=True)
    sha256: Mapped[str] = mapped_column(CHAR(64), index=True)
    mime_type: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int]
    width: Mapped[int]
    height: Mapped[int]
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status"),
        default=ValidationStatus.PENDING,
        server_default="PENDING",
    )
