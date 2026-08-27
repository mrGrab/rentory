from datetime import date
from uuid import UUID

from sqlalchemy.sql.expression import Select
from sqlmodel import func

from core.sqlmodel_query_gateway import SQLModelQueryGateway
from models.client import Client
from models.item_variant import ItemVariant
from models.links import OrderItemLink
from models.order import Order, OrderFilters


def _filter_by_ids(stmt: Select, order_ids: int | list[int] | None) -> Select:
    if not order_ids:
        return stmt
    if isinstance(order_ids, list):
        return stmt.where(Order.id.in_(order_ids))
    return stmt.where(Order.id == order_ids)


def _filter_by_phone(stmt: Select, phone: str | None) -> Select:
    if phone:
        return stmt.join(Client).where(Client.phone.ilike(f"%{phone}%"))
    return stmt


def _filter_by_time_range(stmt: Select, start: date | None, end: date | None) -> Select:
    if start and end:
        return stmt.where(Order.end_time >= start, Order.start_time <= end)
    if end:
        return stmt.where(Order.end_time == end)
    if start:
        return stmt.where(Order.start_time == start)
    return stmt


def _filter_by_item_ids(stmt: Select, item_ids: list[UUID] | None) -> Select:
    if item_ids:
        stmt = stmt.join(Order.item_links).join(OrderItemLink.item_variant)
        return stmt.where(ItemVariant.item_id.in_(item_ids))
    return stmt


def apply_order_filters(stmt: Select, filters: OrderFilters) -> Select:
    """Filter strategy for order queries used by the query gateway module."""

    # Exclude archived by default unless explicitly filtered.
    if filters.is_archived is None:
        stmt = stmt.where(Order.is_archived == False)
    else:
        stmt = stmt.where(Order.is_archived == filters.is_archived)

    if filters.client_id:
        stmt = stmt.where(Order.client_id == filters.client_id)
    if filters.status:
        stmt = stmt.where(Order.status.in_(filters.status))
    if filters.pickup_type:
        stmt = stmt.where(Order.delivery_info["pickup_type"] == filters.pickup_type)

    stmt = _filter_by_ids(stmt, filters.id)
    stmt = _filter_by_phone(stmt, filters.phone)
    stmt = _filter_by_time_range(stmt, filters.start_time, filters.end_time)
    stmt = _filter_by_item_ids(stmt, filters.item_ids)

    if filters.tag:
        stmt = stmt.where(Order.tags.contains([filters.tag]))
    if filters.created_at:
        stmt = stmt.where(func.date(Order.created_at) == filters.created_at.date())

    return stmt.distinct()


class OrderQueryGateway(SQLModelQueryGateway[Order, OrderFilters]):
    def __init__(self, session):
        super().__init__(
            session=session, model=Order, apply_filters=apply_order_filters
        )
