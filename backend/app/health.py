from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_engine

router = APIRouter(tags=["health"])


def database_ready() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


@router.get("/health/live", include_in_schema=False)
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", include_in_schema=False)
def ready() -> JSONResponse:
    if not database_ready():
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "down"})
    return JSONResponse(status_code=200, content={"status": "ready", "database": "up"})
