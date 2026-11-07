from datetime import UTC, date, datetime

from sqlalchemy import Boolean, String, literal
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import FunctionElement

from core.exceptions import BadRequestException


class json_array_contains(FunctionElement):
    """SQL predicate: the JSON array column contains the exact string value.

    Replaces `column.contains(...)`, which SQLAlchemy does not support on JSON
    columns (it falls back to LIKE on the serialized text). Implemented for
    the dialects used by the project: MySQL (production) and SQLite (tests).
    """

    type = Boolean()
    inherit_cache = True

    def __init__(self, column, value: str):
        super().__init__(column, literal(value, String))


@compiles(json_array_contains, "mysql")
def _json_array_contains_mysql(element, compiler, **kw):
    column, value = element.clauses.clauses
    return (
        f"JSON_CONTAINS({compiler.process(column, **kw)}, "
        f"JSON_QUOTE({compiler.process(value, **kw)}))"
    )


@compiles(json_array_contains, "sqlite")
def _json_array_contains_sqlite(element, compiler, **kw):
    column, value = element.clauses.clauses
    return (
        f"EXISTS (SELECT 1 FROM json_each({compiler.process(column, **kw)}) "
        f"WHERE json_each.value = {compiler.process(value, **kw)})"
    )


def ensure_utc(value: datetime) -> datetime:
    """Coerce a datetime to timezone-aware UTC.

    Args:
        value: The datetime to be converted.

    Returns:
        The timezone-aware UTC datetime.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def validate_time_period(start: date, end: date) -> None:
    """
    Validate that a time period's start is not after its end.

    Equal start/end is allowed (e.g. single-day rentals).

    Raises:
        BadRequestException: If start is after end.
    """
    if start > end:
        raise BadRequestException("Start time must be before end time")


def display_title(snapshot: str | None, live_value: str) -> str:
    """Resolve an order line's displayed item title.

    Prefers the historical snapshot captured on the order line; falls back
    to the item's current title when the snapshot is missing or blank.
    """
    return snapshot or live_value


def display_size(snapshot: str | None, live_value: str | None) -> str:
    """Resolve an order line's displayed variant size (see `display_title`).

    Size is optional on a variant, so this falls back to an empty string.
    """
    return snapshot or live_value or ""


def display_color(snapshot: str | None, live_value: str | None) -> str:
    """Resolve an order line's displayed variant color (see `display_title`).

    Color is optional on a variant, so this falls back to an empty string.
    """
    return snapshot or live_value or ""
