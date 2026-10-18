from sqlalchemy.sql.expression import Select
from sqlmodel import Session, col

from core.sqlmodel_query_gateway import SQLModelQueryGateway
from models.item import Item, ItemFilters
from models.item_variant import ItemVariant


def apply_item_filters(
    stmt: Select[tuple[Item]], filters: ItemFilters
) -> Select[tuple[Item]]:
    """Filter strategy for item queries used by the query gateway module."""

    # Exclude archived items by default unless explicit filter is provided.
    if filters.is_archived is None:
        stmt = stmt.where(col(Item.is_archived) == False)
    else:
        stmt = stmt.where(col(Item.is_archived) == filters.is_archived)

    # Join ItemVariant if any variant-specific filters are present.
    if filters.color or filters.size or filters.variant_status:
        stmt = stmt.join(ItemVariant, col(Item.id) == col(ItemVariant.item_id))

    if filters.id:
        stmt = stmt.where(col(Item.id).in_(filters.id))

    if filters.title:
        stmt = stmt.where(col(Item.title).ilike(f"%{filters.title}%"))
    if filters.q:
        stmt = stmt.where(col(Item.title).ilike(f"%{filters.q}%"))

    if filters.category:
        stmt = stmt.where(col(Item.category) == filters.category)
    if filters.status:
        stmt = stmt.where(col(Item.status) == filters.status.value)
    if filters.tag:
        stmt = stmt.where(col(Item.tags).contains(filters.tag))
    if filters.color:
        stmt = stmt.where(col(ItemVariant.color) == filters.color)
    if filters.size:
        stmt = stmt.where(col(ItemVariant.size) == filters.size)
    if filters.variant_status:
        stmt = stmt.where(col(ItemVariant.status) == filters.variant_status)

    return stmt.distinct()


class ItemQueryGateway(SQLModelQueryGateway[Item, ItemFilters]):
    def __init__(self, session: Session):
        super().__init__(session=session, model=Item, apply_filters=apply_item_filters)
