import hashlib
import io
import os
from uuid import uuid4

import pytest
from db.test_schema import database  # noqa: F401
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from visionguard.api.main import create_app
from visionguard.core.config import Settings, get_settings
from visionguard.db.models import MediaAsset
from visionguard.db.session import get_session
from visionguard.media import (
    ImageTooLarge,
    InvalidImage,
    UnsupportedMediaType,
    sanitize_image,
    sniff_mime,
)
from visionguard.storage import FakeObjectStorage, S3ObjectStorage, get_storage


def picture(fmt="PNG", **kwargs):
    stream = io.BytesIO()
    Image.new("RGB", (8, 4), "red").save(stream, format=fmt, **kwargs)
    return stream.getvalue()


@pytest.mark.parametrize(
    "fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
def test_sanitize(fmt, mime):
    data = picture(fmt)
    assert sniff_mime(data[:32]) == mime
    result = sanitize_image(data, max_pixels=100)
    assert result.mime == mime
    assert (result.width, result.height) == (8, 4)
    assert result.sha256 == hashlib.sha256(result.data).hexdigest()
    assert not (
        {"exif", "icc_profile", "xmp", "XML:com.adobe.xmp"}
        & Image.open(io.BytesIO(result.data)).info.keys()
    )


@pytest.mark.parametrize(
    "data,error",
    [(b"text", UnsupportedMediaType), (b"\x89PNG\r\n\x1a\ngarbage", InvalidImage)],
)
def test_invalid(data, error):
    with pytest.raises(error):
        sanitize_image(data, max_pixels=100)


def test_trailer_and_truncation():
    data = picture("JPEG")
    result = sanitize_image(
        data + b"PK\x03\x04<script>secret-trailer</script>", max_pixels=100
    )
    assert b"secret-trailer" not in result.data
    with pytest.raises(InvalidImage):
        sanitize_image(data[: len(data) // 2], max_pixels=100)


def test_pixels_and_metadata():
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "secret-exif"
    exif[34853] = {1: "N", 2: (1, 2, 3)}
    data = picture("JPEG", exif=exif, icc_profile=b"secret-icc", xmp=b"secret-xmp")
    result = sanitize_image(data, max_pixels=32)
    assert (result.width, result.height) == (4, 8)
    assert not Image.open(io.BytesIO(result.data)).getexif()
    for marker in (b"secret-exif", b"secret-icc", b"secret-xmp", b"Exif", b"GPS"):
        assert marker not in result.data
    with pytest.raises(ImageTooLarge):
        sanitize_image(data, max_pixels=31)


@pytest.mark.parametrize("fmt", ["GIF", "PNG", "WEBP"])
def test_animation(fmt):
    stream = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(
        stream,
        format=fmt,
        save_all=True,
        append_images=[Image.new("RGB", (2, 2), "blue")],
        duration=100,
        loop=0,
    )
    with pytest.raises((InvalidImage, UnsupportedMediaType)):
        sanitize_image(stream.getvalue(), max_pixels=100)


@pytest.fixture
def api(database):  # noqa: F811
    engine, _ = database
    storage = FakeObjectStorage()
    app = create_app()
    with engine.connect() as conn:
        transaction = conn.begin()
        with Session(
            conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:

            def sessions():
                yield session

            app.dependency_overrides[get_session] = sessions
            app.dependency_overrides[get_storage] = lambda: storage
            with TestClient(app) as client:
                yield client, session, storage, app
        transaction.rollback()


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_upload(api, fmt, caplog):
    client, session, storage, _ = api
    response = client.post(
        "/api/v1/media",
        files={"file": ("private-name.png", picture(fmt), "text/plain")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    from uuid import UUID

    asset = session.get(MediaAsset, UUID(body["id"]))
    assert (
        asset.sha256
        == body["sha256"]
        == hashlib.sha256(storage.objects[asset.object_key]).hexdigest()
    )
    assert body["size_bytes"] == len(storage.objects[asset.object_key])
    assert client.get("/api/v1/media/" + body["id"]).json() == body
    assert response.headers["X-Request-ID"]
    assert "private-name" not in response.text + caplog.text
    assert "object_key" not in body


@pytest.mark.parametrize(
    "data,status,code",
    [
        (b"text", 415, "unsupported_media_type"),
        (b"\x89PNG\r\n\x1a\ngarbage", 422, "invalid_image"),
        (b"", 400, "missing_file"),
    ],
)
def test_bad_upload(api, data, status, code):
    client, session, storage, _ = api
    before = session.scalar(select(func.count()).select_from(MediaAsset))
    response = client.post("/api/v1/media", files={"file": ("secret.png", data)})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert session.scalar(select(func.count()).select_from(MediaAsset)) == before
    assert not storage.objects


def test_limits_missing_get_and_openapi(api):
    client, _, storage, app = api
    app.dependency_overrides[get_settings] = lambda: Settings(max_upload_bytes=10)
    for headers in ({}, {"Content-Length": "10000"}):
        response = client.post(
            "/api/v1/media", files={"file": ("x", picture())}, headers=headers
        )
        assert response.status_code == 413
    assert not storage.objects
    app.dependency_overrides.pop(get_settings)
    assert client.post("/api/v1/media").json()["error"]["code"] == "missing_file"
    assert client.get(f"/api/v1/media/{uuid4()}").status_code == 404
    assert (
        client.get("/api/v1/media/wrong").json()["error"]["code"] == "validation_error"
    )
    assert "/api/v1/media/{id}" in client.get("/openapi.json").json()["paths"]


def test_db_failure_compensates(api, monkeypatch):
    client, session, storage, _ = api

    def fail():
        raise RuntimeError("secret-db-error")

    monkeypatch.setattr(session, "commit", fail)
    response = client.post("/api/v1/media", files={"file": ("x", picture())})
    assert response.status_code == 500
    assert "secret-db-error" not in response.text
    assert not storage.objects


@pytest.mark.s3
def test_real_s3():
    if os.getenv("SKIP_S3_TESTS") == "1":
        pytest.skip("SKIP_S3_TESTS=1")
    storage = S3ObjectStorage(Settings())
    key = f"test/{uuid4()}.png"
    try:
        storage.put_bytes(key, picture(), "image/png")
        assert storage.exists(key)
    finally:
        storage.delete(key)
    assert not storage.exists(key)


def test_stream_without_content_length(api):
    client, _, storage, app = api
    app.dependency_overrides[get_settings] = lambda: Settings(max_upload_bytes=250)
    boundary = "test-boundary"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="x"\r\n\r\n'
        ).encode()
        + b"a" * 300
        + f"\r\n--{boundary}--\r\n".encode()
    )
    response = client.post(
        "/api/v1/media",
        content=iter([body[:100], body[100:]]),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    assert response.status_code == 413
    assert not storage.objects


def test_png_text_removed_and_bomb_warning(monkeypatch):
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("secret", "private-text")
    result = sanitize_image(picture(pnginfo=info), max_pixels=32)
    assert b"private-text" not in result.data
    assert not Image.open(io.BytesIO(result.data)).info
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 20)
    with pytest.raises(ImageTooLarge):
        sanitize_image(picture(), max_pixels=1000)
    assert Image.MAX_IMAGE_PIXELS == 20
