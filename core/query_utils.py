# Query utilities

# --- Core Imports ---
import json
from typing import List
from fastapi import Response
from sqlmodel import Session, select, func

# --- Project Imports ---
from core.logger import logger
from core.exceptions import AuthenticationException


def parse_params(filter_str: str, range_str: str, sort_str: str) -> tuple:
    """Parses and validates list query parameters from JSON strings."""
    try:
        filters = json.loads(filter_str)
        range_list = json.loads(range_str)
        sort_field, sort_order = json.loads(sort_str)
        return filters, range_list, sort_field, sort_order.upper()
    except (json.JSONDecodeError) as e:
        raise AuthenticationException(f"Invalid query parameters format: {e}")


def calculate_pagination(range_list: List[int]) -> tuple[int, int]:
    """Calculates offset and limit for a database query from a range list."""
    offset = range_list[0]
    limit = range_list[1] - range_list[0] + 1
    return offset, limit


def apply_sorting(stmt, model: object, sort_field: str, sort_order: str):
    """Applies sorting to a SQLAlchemy statement."""
    try:
        sort_column = getattr(model, sort_field)
        if sort_order == "ASC":
            return stmt.order_by(sort_column.asc())
        # Default to DESC for safety
        return stmt.order_by(sort_column.desc())
    except AttributeError:
        logger.warning(
            f"Invalid sort field '{sort_field}', using default sorting.")
        # Fallback to a default sort order, e.g., by creation date
        if hasattr(model, "created_at"):
            return stmt.order_by(model.created_at.desc())
        return stmt


def get_total_count(session: Session, stmt) -> int:
    """Executes a count query to get the total number of records."""
    count_stmt = select(func.count()).select_from(stmt.subquery())
    return session.exec(count_stmt).one()


def set_pagination_headers(response: Response, offset: int, count: int,
                           total: int):
    """Sets standard pagination headers on the response."""
    end_index = offset + count - 1 if count > 0 else offset
    content_range = f"items {offset}-{end_index}/{total}"
    response.headers["Content-Range"] = content_range
    response.headers["X-Total-Count"] = str(total)
    response.headers[
        "Access-Control-Expose-Headers"] = "Content-Range, X-Total-Count"
