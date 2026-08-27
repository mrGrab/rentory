from typing import Any, Protocol


class QueryGateway[TModel, TFilters](Protocol):
    """Query-focused interface used by domain modules."""

    def get_by_id(self, object_id: Any) -> TModel | None: ...

    def list(
        self,
        filters: TFilters,
        offset: int = 0,
        limit: int = 100,
        sort_field: str = "id",
        sort_order: str = "ASC",
    ) -> tuple[list[TModel], int]: ...
