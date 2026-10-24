from collections.abc import Callable
from contextlib import closing
from functools import lru_cache
from typing import Annotated, Literal

import boto3
import redis
from botocore.config import Config
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from visionguard.core.config import get_settings

router = APIRouter()
ReadinessChecks = dict[str, Callable[[], None]]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class CheckResults(BaseModel):
    database: Literal["ok", "fail"]
    redis: Literal["ok", "fail"]
    storage: Literal["ok", "fail"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: CheckResults


def check_database() -> None:
    engine = create_engine(
        get_settings().database_url,
        poolclass=NullPool,
        connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def check_redis() -> None:
    with redis.Redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
        retry_on_timeout=False,
    ) as client:
        if not client.ping():
            raise RuntimeError("Redis ping failed")


def check_storage() -> None:
    settings = get_settings()
    with closing(
        boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            region_name=settings.s3_region,
            config=Config(
                connect_timeout=2,
                read_timeout=2,
                retries={"total_max_attempts": 1},
                s3={"addressing_style": "path"},
            ),
        )
    ) as client:
        client.head_bucket(Bucket=settings.s3_bucket)


@lru_cache
def get_readiness_checks() -> ReadinessChecks:
    return {
        "database": check_database,
        "redis": check_redis,
        "storage": check_storage,
    }


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/ready", response_model=ReadyResponse, responses={503: {"model": ReadyResponse}}
)
def ready(
    response: Response,
    checks: Annotated[ReadinessChecks, Depends(get_readiness_checks)],
) -> ReadyResponse:
    results = {}
    for name in ("database", "redis", "storage"):
        try:
            checks[name]()
            results[name] = "ok"
        except Exception:
            # Dependency errors may contain connection strings and credentials.
            results[name] = "fail"
    degraded = "fail" in results.values()
    response.status_code = 503 if degraded else 200
    return ReadyResponse(
        status="degraded" if degraded else "ready", checks=CheckResults(**results)
    )
