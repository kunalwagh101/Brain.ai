import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_engine
from app.observability import DependencyCheck, record_dependency_check

router = APIRouter(tags=["health"])


def database_readiness() -> DependencyCheck:
    started = time.perf_counter()
    ready = False
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        ready = True
    except SQLAlchemyError:
        ready = False
    duration = max(0.0, time.perf_counter() - started)
    record_dependency_check("database", ready=ready, duration_seconds=duration)
    return DependencyCheck(
        name="database",
        ready=ready,
        latency_ms=round(duration * 1000),
    )


def database_ready() -> bool:
    return database_readiness().ready


@router.get("/health/live", include_in_schema=False)
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", include_in_schema=False)
def ready() -> JSONResponse:
    database = database_readiness()
    content = {
        "status": "ready" if database.ready else "not_ready",
        "dependencies": {
            database.name: {
                "status": "up" if database.ready else "down",
                "latency_ms": database.latency_ms,
            }
        },
    }
    return JSONResponse(status_code=200 if database.ready else 503, content=content)
