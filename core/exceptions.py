"""
Domain error classes raised by service modules.

These carry no HTTP knowledge; api/errors.py maps each class to a status code
and response body in one place.
"""

from dataclasses import asdict, dataclass
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException, status


class AppError(Exception):
    """Base class for domain errors."""

    default_message: str = "Application error"

    def __init__(
        self, message: str | None = None, errors: list[dict[str, Any]] | None = None
    ):
        self.message: str = message or self.default_message
        self.errors: list[dict[str, Any]] | None = errors
        super().__init__(self.message)


class BadRequestException(AppError):
    """The request is invalid."""

    default_message: str = "Bad Request"


class NotFoundException(AppError):
    """The requested resource does not exist."""

    default_message: str = "The requested resource was not found"


class ConflictException(AppError):
    """The request conflicts with current data."""

    default_message: str = "Conflict"


class InternalErrorException(AppError):
    """Server-side failure, such as inconsistent stored data."""

    default_message: str = "An unexpected internal error occurred"


ShortfallReason = Literal["archived", "capacity", "not_found", "wrong_item"]


@dataclass(frozen=True)
class Shortfall:
    """Why one Order line cannot be booked."""

    variant_id: UUID
    reason: ShortfallReason
    requested: int
    available: int | None = None
    item_id: UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["variant_id"] = str(self.variant_id)
        data["item_id"] = str(self.item_id) if self.item_id else None
        return data

    def message(self) -> str:
        if self.reason == "not_found":
            return f"Variant {self.variant_id} not found"
        if self.reason == "wrong_item":
            return f"Variant {self.variant_id} does not belong to item {self.item_id}"
        if self.reason == "archived":
            return (
                f"Variant {self.variant_id}: 0 unit(s) available; "
                + "archived variants cannot be added or increased"
            )
        return (
            f"Variant {self.variant_id}: {self.available} unit(s) available, "
            + f"requested {self.requested}"
        )


class UnavailableError(ConflictException):
    """One or more Order lines cannot be booked."""

    def __init__(self, shortfalls: list[Shortfall]):
        self.shortfalls: list[Shortfall] = shortfalls
        super().__init__(
            "; ".join(s.message() for s in shortfalls),
            errors=[s.to_dict() for s in shortfalls],
        )


# ---------- HTTP-level errors (auth), not domain errors ----------
# Auth code is out of scope for the domain-error migration; these stay
# HTTPException subclasses so FastAPI renders them, headers included.


class AuthenticationException(HTTPException):
    """HTTP 401 Unauthorized."""

    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionException(HTTPException):
    """HTTP 403 Forbidden."""

    def __init__(
        self, detail: str = "You do not have permission to perform this action"
    ):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
