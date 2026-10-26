from threading import Lock

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from core.database import SessionDep
from core.logger import logger

router = APIRouter(tags=["System"])

# Allows one health check at a time, so a hung database blocks one thread at most
_health_lock = Lock()


@router.get(
    path="/health",
    summary="Health check",
    response_description="Application and database availability",
)
def health(session: SessionDep) -> JSONResponse:
    """
    Checks that the application can reach the database via a pooled connection.
    """
    if not _health_lock.acquire(blocking=False):
        logger.warning("Health check skipped: previous check still running")
        return _unavailable()
    try:
        _ = session.connection().execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check failed: database unavailable")
        return _unavailable()
    finally:
        _health_lock.release()
    return JSONResponse(content={"status": "ok"})


def _unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "error", "database": "unavailable"},
    )


@router.get(
    path="/version",
    summary="Get application version",
    response_description="Current version of the application",
)
async def read_version() -> JSONResponse:
    """
    Returns the current version of the application as defined in settings.
    """
    return JSONResponse(content={"version": settings.VERSION})
