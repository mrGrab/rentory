from sqlalchemy.sql.expression import Select

from core.sqlmodel_query_gateway import SQLModelQueryGateway
from models.item import Item, ItemFilters
from models.item_variant import ItemVariant


def apply_item_filters(stmt: Select, filters: ItemFilters) -> Select:
    """Filter strategy for item queries used by the query gateway module."""

    # Exclude archived items by default unless explicit filter is provided.
    if filters.is_archived is None:
        stmt = stmt.where(Item.is_archived == False)
    else:
        stmt = stmt.where(Item.is_archived == filters.is_archived)

    # Join ItemVariant if any variant-specific filters are present.
    if any([filters.color, filters.size, filters.variant_status]):
        stmt = stmt.join(ItemVariant, Item.id == ItemVariant.item_id)

    if filters.id:
        if isinstance(filters.id, list):
            stmt = stmt.where(Item.id.in_(filters.id))
        else:
            stmt = stmt.where(Item.id.contains(filters.id))

    if filters.title:
        stmt = stmt.where(Item.title.ilike(f"%{filters.title}%"))
    if filters.q:
        stmt = stmt.where(Item.title.ilike(f"%{filters.q}%"))

    if filters.category:
        stmt = stmt.where(Item.category == filters.category)
    if filters.status:
        stmt = stmt.where(Item.status == filters.status.value)
    if filters.tag:
        stmt = stmt.where(Item.tags.contains(filters.tag))
    if filters.color:
        stmt = stmt.where(ItemVariant.color == filters.color)
    if filters.size:
        stmt = stmt.where(ItemVariant.size == filters.size)
    if filters.variant_status:
        stmt = stmt.where(ItemVariant.status == filters.variant_status)

    return stmt.distinct()


class ItemQueryGateway(SQLModelQueryGateway[Item, ItemFilters]):
    def __init__(self, session):
        super().__init__(session=session, model=Item, apply_filters=apply_item_filters)
