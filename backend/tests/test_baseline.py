import json
import logging

import pytest
from fastapi.testclient import TestClient

from visionguard.api.main import create_app
from visionguard.api.routes.health import get_readiness_checks
from visionguard.core.config import Settings, get_settings
from visionguard.core.logging import JsonFormatter


def test_settings_defaults_and_override(monkeypatch):
    monkeypatch.delenv("MAX_UPLOAD_BYTES", raising=False)
    assert Settings().max_upload_bytes == 10 * 1024 * 1024
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1234")
    monkeypatch.setenv("APP_ENV", "test")
    assert Settings().max_upload_bytes == 1234
    assert Settings().app_env == "test"
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()


def test_settings_reject_invalid_upload_limit():
    with pytest.raises(ValueError):
        Settings(max_upload_bytes=0)


@pytest.fixture
def app():
    return create_app()


def test_health_and_request_id(app):
    def unexpected_check():
        raise AssertionError("Liveness must not resolve readiness dependencies")

    app.dependency_overrides[get_readiness_checks] = unexpected_check
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "test-123"})
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response.headers["X-Request-ID"] == "test-123"
        assert client.get("/health").headers["X-Request-ID"]


def test_invalid_request_id_is_replaced(app):
    from uuid import UUID

    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "x" * 129})
    assert (
        str(UUID(response.headers["X-Request-ID"])) == response.headers["X-Request-ID"]
    )


@pytest.mark.parametrize("failed", [None, "database", "redis", "storage"])
def test_ready(app, failed):
    def ok():
        return None

    def fail():
        raise RuntimeError("secret-password credential-endpoint")

    app.dependency_overrides[get_readiness_checks] = lambda: {
        name: fail if name == failed else ok
        for name in ("database", "redis", "storage")
    }
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == (503 if failed else 200)
    assert response.json() == {
        "status": "degraded" if failed else "ready",
        "checks": {
            name: "fail" if name == failed else "ok"
            for name in ("database", "redis", "storage")
        },
    }
    assert "secret" not in response.text
    assert "credential" not in response.text


@pytest.mark.parametrize(
    "path,code", [("/missing", "http_error"), ("/boom", "internal_error")]
)
def test_error_shape(app, path, code):
    @app.get("/boom")
    def boom():
        raise RuntimeError("secret-password")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(path, headers={"X-Request-ID": "error-123"})
    assert response.status_code == (404 if path == "/missing" else 500)
    assert set(response.json()["error"]) == {"code", "message", "request_id"}
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["request_id"] == "error-123"
    assert response.headers["X-Request-ID"] == "error-123"
    assert "secret" not in response.text


def test_validation_error_shape(app):
    @app.get("/number")
    def number(value: int):
        return value

    with TestClient(app) as client:
        response = client.get("/number?value=secret-password")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "secret" not in response.text


def test_json_logging_request_id(app, caplog):
    with caplog.at_level(logging.INFO, logger="visionguard.requests"):
        with TestClient(app) as client:
            client.get("/health", headers={"X-Request-ID": "log-123"})
    records = [r for r in caplog.records if r.name == "visionguard.requests"]
    assert records
    payload = json.loads(JsonFormatter().format(records[-1]))
    assert payload["request_id"] == "log-123"
    assert payload["status_code"] == 200


def test_celery_configuration_and_ping():
    from workers.celery_app import app, ping

    assert app.conf.task_acks_late is True
    assert app.conf.task_default_queue == "inference"
    assert app.conf.broker_url == get_settings().redis_url
    assert ping.run() == "pong"
