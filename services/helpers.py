from datetime import UTC, date, datetime

from core.exceptions import BadRequestException


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
