from sqlalchemy.sql.expression import Select

from core.sqlmodel_query_gateway import SQLModelQueryGateway
from models.item_variant import ItemVariant, ItemVariantFilters


def apply_item_variant_filters(stmt: Select, filters: ItemVariantFilters) -> Select:
    """Filter strategy for item variant queries used by query gateway."""

    # Exclude archived variants by default unless explicitly filtered.
    if filters.is_archived is None:
        stmt = stmt.where(ItemVariant.is_archived == False)
    else:
        stmt = stmt.where(ItemVariant.is_archived == filters.is_archived)

    if filters.id:
        stmt = stmt.where(ItemVariant.id.in_(filters.id))
    if filters.item_id:
        stmt = stmt.where(ItemVariant.item_id.in_(filters.item_id))
    if filters.color:
        stmt = stmt.where(ItemVariant.color == filters.color)
    if filters.size:
        stmt = stmt.where(ItemVariant.size == filters.size)
    if filters.status:
        stmt = stmt.where(ItemVariant.status.in_(filters.status))
    if filters.service_end_time:
        stmt = stmt.where(ItemVariant.service_end_time == filters.service_end_time)
    if filters.service_start_time:
        stmt = stmt.where(ItemVariant.service_start_time == filters.service_start_time)

    return stmt.distinct()


class ItemVariantQueryGateway(SQLModelQueryGateway[ItemVariant, ItemVariantFilters]):
    def __init__(self, session):
        super().__init__(
            session=session, model=ItemVariant, apply_filters=apply_item_variant_filters
        )
