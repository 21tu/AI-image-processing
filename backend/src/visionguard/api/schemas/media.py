from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from visionguard.db.enums import ValidationStatus


class MediaAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    mime_type: str
    size_bytes: int
    width: int
    height: int
    sha256: str
    validation_status: ValidationStatus
    created_at: datetime
