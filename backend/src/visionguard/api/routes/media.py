import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from visionguard.api.schemas.media import MediaAssetResponse
from visionguard.core.config import Settings, get_settings
from visionguard.db.enums import ValidationStatus
from visionguard.db.models import MediaAsset
from visionguard.db.session import get_session
from visionguard.media import InvalidImage, UnsupportedMediaType, sanitize_image
from visionguard.storage import ObjectStorage, get_storage

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger("visionguard.media")


def failure(request, status, code, message):
    from visionguard.api.main import error_response

    return error_response(request, status, code, message)


@router.post(
    "/media",
    response_model=MediaAssetResponse,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def upload_media(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
    session: Annotated[Session, Depends(get_session)],
):
    def too_large():
        return failure(request, 413, "payload_too_large", "Upload exceeds size limit")

    length = request.headers.get("content-length")
    if length and length.isdecimal() and int(length) > settings.max_upload_bytes:
        return too_large()
    # Limit raw multipart input too, including requests without Content-Length.
    received = 0
    original_receive = request._receive

    async def limited_receive():
        nonlocal received
        message = await original_receive()
        received += len(message.get("body", b""))
        if received > settings.max_upload_bytes:
            raise UploadLimitExceeded()
        return message

    request._receive = limited_receive
    try:
        async with request.form(max_files=1, max_fields=0) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile):
                return failure(
                    request, 400, "missing_file", "A non-empty file is required"
                )
            data = bytearray()
            while chunk := await file.read(64 * 1024):
                data.extend(chunk)
                if len(data) > settings.max_upload_bytes:
                    return too_large()
            if not data:
                return failure(
                    request, 400, "missing_file", "A non-empty file is required"
                )
    except UploadLimitExceeded:
        return too_large()
    except Exception:
        return failure(request, 400, "missing_file", "Invalid multipart upload")
    try:
        image = await run_in_threadpool(
            sanitize_image, bytes(data), max_pixels=settings.max_image_pixels
        )
    except UnsupportedMediaType:
        return failure(request, 415, "unsupported_media_type", "Unsupported image type")
    except InvalidImage:
        return failure(request, 422, "invalid_image", "Invalid image")
    asset_id = uuid4()
    key = f"media/{asset_id}.{image.ext}"
    asset = MediaAsset(
        id=asset_id,
        object_key=key,
        sha256=image.sha256,
        mime_type=image.mime,
        size_bytes=len(image.data),
        width=image.width,
        height=image.height,
        validation_status=ValidationStatus.VALID,
    )
    try:
        await run_in_threadpool(storage.put_bytes, key, image.data, image.mime)
        session.add(asset)
        session.flush()
        result = MediaAssetResponse.model_validate(asset)
        session.commit()
    except Exception:
        session.rollback()
        try:
            await run_in_threadpool(storage.delete, key)
        except Exception:
            logger.warning("media_cleanup_failed", extra={"asset_id": str(asset_id)})
        return failure(request, 500, "internal_error", "Unable to store image")
    logger.info(
        "media_created",
        extra={
            "asset_id": str(asset_id),
            "sha256": image.sha256,
            "size_bytes": len(image.data),
            "mime": image.mime,
        },
    )
    return result


class UploadLimitExceeded(Exception):
    pass


@router.get("/media/{id}", response_model=MediaAssetResponse)
def get_media(
    id: UUID, request: Request, session: Annotated[Session, Depends(get_session)]
):
    asset = session.get(MediaAsset, id)
    if asset is None:
        return failure(request, 404, "not_found", "Media asset not found")
    return asset
