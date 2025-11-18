from datetime import date, datetime
from core.exceptions import BadRequestException


def validate_time_period(start: date | datetime | None,
                         end: date | datetime | None) -> None:
    """
    Validate that both start and end dates/times are provided and logically ordered.

    Raises:
        BadRequestException: If any validation rule is violated.
    """
    if not start:
        raise BadRequestException("Start time is required")

    if not end:
        raise BadRequestException("End time is required")

    # Normalize to datetime for consistent comparison if mixing date and datetime
    if isinstance(start, date) and not isinstance(start, datetime):
        start = datetime.combine(start, datetime.min.time())
    if isinstance(end, date) and not isinstance(end, datetime):
        end = datetime.combine(end, datetime.min.time())

    if start == end:
        raise BadRequestException("Start and end times cannot be the same")

    if start > end:
        raise BadRequestException("Start time must be before end time")
