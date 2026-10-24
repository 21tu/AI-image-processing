import logging
import re
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from visionguard.api.routes.health import router
from visionguard.core.config import get_settings
from visionguard.core.logging import setup_logging

logger = logging.getLogger("visionguard.requests")
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(request: Request, status: int, code: str, message: str):
    request_id = request.state.request_id
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(
            error=ErrorDetail(code=code, message=message, request_id=request_id)
        ).model_dump(),
        headers={"X-Request-ID": request_id},
    )


def create_app() -> FastAPI:
    setup_logging(get_settings().log_level)
    app = FastAPI(title="VisionGuard", version="0.1.0")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        supplied_id = request.headers.get("X-Request-ID", "")
        request.state.request_id = (
            supplied_id if REQUEST_ID_PATTERN.fullmatch(supplied_id) else str(uuid4())
        )
        try:
            response = await call_next(request)
        except Exception:
            response = error_response(
                request, 500, "internal_error", "Internal server error"
            )
        response.headers["X-Request-ID"] = request.state.request_id
        logger.info(
            "request_completed",
            extra={
                "request_id": request.state.request_id,
                "status_code": response.status_code,
            },
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        # Do not expose arbitrary exception details from future routes.
        response = error_response(
            request, exc.status_code, "http_error", "Request failed"
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error_response(
            request, 422, "validation_error", "Request validation failed"
        )

    app.include_router(router)
    return app


app = create_app()
