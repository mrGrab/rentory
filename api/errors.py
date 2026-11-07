"""The one place that maps domain errors (core/exceptions.py) to HTTP."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from core.exceptions import (
    AppError,
    BadRequestException,
    ConflictException,
    InternalErrorException,
    NotFoundException,
)
from core.logger import logger

STATUS_BY_ERROR: dict[type[AppError], int] = {
    BadRequestException: status.HTTP_400_BAD_REQUEST,
    NotFoundException: status.HTTP_404_NOT_FOUND,
    ConflictException: status.HTTP_409_CONFLICT,
    InternalErrorException: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def status_for(error: AppError) -> int:
    """Status of the nearest mapped class in the error's hierarchy; else 500."""
    for cls in type(error).__mro__:
        if cls in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[cls]
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    status_code = status_for(exc)
    if status_code >= 500:
        logger.error(
            f"{type(exc).__name__} on {request.method} {request.url.path}: "
            + exc.message,
            exc_info=exc,
        )
    body: dict[str, Any] = {"detail": exc.message}
    if exc.errors is not None:
        body["errors"] = exc.errors
    return JSONResponse(status_code=status_code, content=body)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
