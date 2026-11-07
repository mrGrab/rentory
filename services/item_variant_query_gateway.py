from sqlalchemy.sql.expression import Select
from sqlmodel import Session, col

from core.sqlmodel_query_gateway import SQLModelQueryGateway
from models.item_variant import ItemVariant, ItemVariantFilters


def apply_item_variant_filters(
    stmt: Select[tuple[ItemVariant]], filters: ItemVariantFilters
) -> Select[tuple[ItemVariant]]:
    """Filter strategy for item variant queries used by query gateway."""

    # Exclude archived variants by default unless explicitly filtered.
    if filters.is_archived is None:
        stmt = stmt.where(col(ItemVariant.is_archived) == False)
    else:
        stmt = stmt.where(col(ItemVariant.is_archived) == filters.is_archived)

    if filters.id:
        stmt = stmt.where(col(ItemVariant.id).in_(filters.id))
    if filters.item_id:
        stmt = stmt.where(col(ItemVariant.item_id).in_(filters.item_id))
    if filters.color:
        stmt = stmt.where(col(ItemVariant.color) == filters.color)
    if filters.size:
        stmt = stmt.where(col(ItemVariant.size) == filters.size)
    if filters.status:
        stmt = stmt.where(col(ItemVariant.status).in_(filters.status))
    if filters.service_end_time:
        stmt = stmt.where(col(ItemVariant.service_end_time) == filters.service_end_time)
    if filters.service_start_time:
        stmt = stmt.where(
            col(ItemVariant.service_start_time) == filters.service_start_time
        )

    return stmt.distinct()


class ItemVariantQueryGateway(SQLModelQueryGateway[ItemVariant, ItemVariantFilters]):
    def __init__(self, session: Session):
        super().__init__(
            session=session, model=ItemVariant, apply_filters=apply_item_variant_filters
        )
