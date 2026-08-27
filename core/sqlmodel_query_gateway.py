from collections.abc import Callable
from typing import Any

from sqlmodel import select

from core.database import get_total_count
from core.query_utils import apply_sorting


class SQLModelQueryGateway[TModel, TFilters]:
    """Reusable SQLModel query implementation with a filter strategy hook."""

    def __init__(
        self,
        session,
        model: type[TModel],
        apply_filters: Callable[[Any, TFilters], Any],
    ):
        self.session = session
        self.model = model
        self.apply_filters = apply_filters

    def get_by_id(self, object_id: Any) -> TModel | None:
        return self.session.get(self.model, object_id)

    def list(
        self,
        filters: TFilters,
        offset: int = 0,
        limit: int = 100,
        sort_field: str = "id",
        sort_order: str = "ASC",
    ) -> tuple[list[TModel], int]:
        stmt = select(self.model)
        stmt = self.apply_filters(stmt, filters)
        # TODO: Move apply sorting logic to this module
        stmt = apply_sorting(stmt, self.model, sort_field, sort_order)

        total = get_total_count(self.session, stmt)
        stmt = stmt.offset(offset).limit(limit)
        rows = self.session.exec(stmt).all()

        return rows, total
