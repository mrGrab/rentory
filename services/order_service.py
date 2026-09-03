from datetime import UTC, date, datetime
from uuid import UUID

from sqlmodel import Session, select

from core.exceptions import BadRequestException, ConflictException

# --- Project Imports ---
from core.logger import logger
from core.query_gateway import QueryGateway
from models.client import Client
from models.item_variant import ItemVariant, ItemVariantPrice, ItemVariantQuantity
from models.links import OrderItemLink
from models.order import (
    Order,
    OrderCreate,
    OrderFilters,
    OrderStatus,
    OrderUpdate,
)
from models.payment import Payment, PaymentBase
from services.helpers import validate_time_period
from services.item_variant_service import ItemVariantService
from services.order_query_gateway import OrderQueryGateway


class OrderService:
    """Business logic for order operations"""

    def __init__(self, session):
        self.session: Session = session
        self.item_variant_service = ItemVariantService(session)
        self.query_gateway: QueryGateway[Order, OrderFilters] = OrderQueryGateway(
            session
        )

    def get_by_id(self, order_id: int) -> Order | None:
        """Get order by ID"""
        logger.debug(f"Fetching order by ID: {order_id}")
        return self.query_gateway.get_by_id(order_id)

    def get_orders(
        self,
        filters: OrderFilters,
        offset: int = 0,
        limit: int = 100,
        sort_field: str = "created_at",
        sort_order: str = "DESC",
    ) -> tuple[list[Order], int]:
        """Get filtered and paginated orders with total count"""
        logger.debug("Fetching orders")
        orders, total = self.query_gateway.list(
            filters=filters,
            offset=offset,
            limit=limit,
            sort_field=sort_field,
            sort_order=sort_order,
        )

        logger.debug(f"Found {len(orders)} orders out of {total} total")
        return orders, total

    def check_variant_availability(
        self,
        variant_id: UUID,
        start_time: date,
        end_time: date,
        requested_quantity: int = 1,
        exclude_order_id: int | None = None,
    ) -> tuple[bool, str | None]:
        """Check if variant is available for booking period.

        Delegates the actual availability math (archived/maintenance/bookings)
        to ItemVariantService, the single source of truth for that logic.
        """
        variant: ItemVariant = self.session.get(ItemVariant, variant_id)
        if not variant:
            return False, f"Variant {variant_id} not found"

        _, available_quantity, _ = self.item_variant_service.check_availability(
            variant, start_time, end_time, exclude_order_id
        )

        if available_quantity < requested_quantity:
            message = (
                f"Variant {variant_id}: {available_quantity} unit(s) available, "
                f"requested {requested_quantity}"
            )
            return False, message

        return True, None

    def validate_order_items(
        self,
        items: list[ItemVariantQuantity],
        start_time: date,
        end_time: date,
        exclude_order_id: int | None = None,
        existing_links: dict[UUID, OrderItemLink] | None = None,
    ) -> None:
        """Validate all items in order are available"""
        if not items:
            raise BadRequestException("Order must contain at least one item")

        unavailable_variants = []

        for item in items:
            variant = self.session.get(ItemVariant, item.item_variant_id)
            if variant is None:
                unavailable_variants.append(f"Variant {item.item_variant_id} not found")
                continue
            if variant.item_id != item.item_id:
                unavailable_variants.append(
                    f"Variant {item.item_variant_id} does not belong to item {item.item_id}"
                )
                continue
            existing_link = (
                existing_links.get(item.item_variant_id) if existing_links else None
            )
            if variant.is_archived and (
                existing_link is None or item.quantity != existing_link.quantity
            ):
                unavailable_variants.append(
                    f"Variant {item.item_variant_id}: 0 unit(s) available; "
                    + "archived variants cannot be added or increased"
                )
                continue
            is_available, reason = self.check_variant_availability(
                variant_id=item.item_variant_id,
                start_time=start_time,
                end_time=end_time,
                requested_quantity=item.quantity,
                exclude_order_id=exclude_order_id,
            )

            if not is_available:
                unavailable_variants.append(reason)

        if unavailable_variants:
            error_msg = "; ".join(unavailable_variants)
            logger.warning(f"Validation failed: {error_msg}")
            raise ConflictException(error_msg)

    def create(self, order_in: OrderCreate) -> Order:
        """Create a new order"""
        logger.debug(f"Creating order for client {order_in.client_id}")

        # Validate dates
        validate_time_period(order_in.start_time, order_in.end_time)

        # Validate item availability
        self.validate_order_items(
            items=order_in.items,
            start_time=order_in.start_time,
            end_time=order_in.end_time,
        )

        # Zero deposit for trusted clients
        client = self.session.get(Client, order_in.client_id)
        if client and client.is_trusted:
            order_in.deposit_amount = 0

        # Create the order
        order_data = order_in.model_dump(
            exclude={"items", "payments"}, exclude_unset=True
        )
        order = Order(**order_data)

        # Create order-item links
        order.item_links = [self._build_order_link(item) for item in order_in.items]

        # Create payments if provided
        if order_in.payments:
            order.payments = [
                Payment(**payment.model_dump()) for payment in order_in.payments
            ]

        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)

        logger.info(f"Order {order.id} created successfully")
        return order

    def update(self, order: Order, order_in: OrderUpdate) -> Order:
        """Update existing order"""
        logger.debug(f"Updating order: {order.id}")

        update_data = order_in.model_dump(
            exclude={"items", "payments"}, exclude_unset=True
        )

        if not update_data and not order_in.items and order_in.payments is None:
            logger.warning("No data provided for update")
            raise BadRequestException("No data provided for update")

        # Get effective dates for validation
        start_time, end_time = self._resolve_effective_dates(order, order_in)
        validate_time_period(start_time, end_time)

        existing_links = {link.item_variant_id: link for link in order.item_links}
        self._validate_updated_items(
            order, order_in, start_time, end_time, existing_links
        )

        # Update order fields
        for field, value in update_data.items():
            setattr(order, field, value)

        # Zero deposit for trusted clients (enforced after field update)
        client = self.session.get(Client, order.client_id)
        if client and client.is_trusted:
            order.deposit_amount = 0

        # Update items if provided
        if order_in.items is not None:
            order.item_links = [
                self._build_order_link(item, existing_links.get(item.item_variant_id))
                for item in order_in.items
            ]

        # Update payments if provided
        if order_in.payments is not None:
            order.payments = self._merge_payments(order.payments, order_in.payments)

        order.updated_at = datetime.now(UTC)
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)

        logger.info(f"Order {order.id} updated successfully")
        return order

    def archive(self, order: Order) -> None:
        """Archive an order (soft delete)"""
        logger.debug(f"Archiving order: {order.id}")

        order.is_archived = True
        order.updated_at = datetime.now(UTC)

        self.session.add(order)
        self.session.commit()

        logger.info(f"Order {order.id} archived successfully")

    def delete(self, order: Order) -> None:
        """Delete an order"""

        logger.debug(f"Deleting order: {order.id}")

        self.session.delete(order)
        self.session.commit()

        logger.info(f"Order {order.id} deleted successfully")

    def get_orders_by_client(self, client_id: UUID) -> list[Order]:
        """Get all orders for a specific client"""
        logger.debug(f"Fetching orders for client: {client_id}")

        stmt = select(Order).where(Order.client_id == client_id)
        orders = self.session.exec(stmt).all()

        logger.debug(f"Found {len(orders)} orders for client {client_id}")
        return list(orders)

    def get_orders_by_status(self, status: str) -> list[Order]:
        """Get all orders with a specific status"""
        logger.debug(f"Fetching orders with status: {status}")

        stmt = select(Order).where(Order.status == status)
        orders = self.session.exec(stmt).all()

        logger.debug(f"Found {len(orders)} orders with status {status}")
        return list(orders)

    def _build_order_link(
        self,
        item: ItemVariantQuantity,
        existing_link: OrderItemLink | None = None,
    ) -> OrderItemLink:
        variant = self.session.get(ItemVariant, item.item_variant_id)
        if variant is None or variant.item_id != item.item_id:
            raise BadRequestException("Selected variant does not belong to the item")
        if variant.id is None or variant.item is None:
            raise BadRequestException("Selected variant is incomplete")

        price = item.price
        deposit = item.deposit
        price_type_snapshot = None
        if item.item_variant_price_id is not None:
            tier = self.session.get(ItemVariantPrice, item.item_variant_price_id)
            if tier is None or tier.variant_id != variant.id:
                raise BadRequestException(
                    "Selected price tier does not belong to the selected variant"
                )
            price = tier.amount
            deposit = tier.deposit
            price_type_snapshot = tier.price_type

        return OrderItemLink(
            item_variant_id=variant.id,
            price=price,
            deposit=deposit,
            quantity=item.quantity,
            item_title_snapshot=(
                existing_link.item_title_snapshot
                if existing_link
                else variant.item.title
            ),
            variant_size_snapshot=(
                existing_link.variant_size_snapshot if existing_link else variant.size
            ),
            variant_color_snapshot=(
                existing_link.variant_color_snapshot if existing_link else variant.color
            ),
            price_type_snapshot=price_type_snapshot,
        )

    def _merge_payments(
        self,
        existing_payments: list[Payment],
        incoming_payments: list[PaymentBase],
    ) -> list[Payment]:
        """Reconcile the incoming payment list with existing rows.

        Payments referenced by `id` are updated in place (so `created_at`
        survives untouched unless a field actually changes); payments with no
        `id` are created fresh. Existing payments omitted from the incoming
        list are dropped via the relationship's delete-orphan cascade.
        """
        existing_by_id = {payment.id: payment for payment in existing_payments}
        merged: list[Payment] = []

        for payment_in in incoming_payments:
            if payment_in.id is None:
                merged.append(Payment(**payment_in.model_dump(exclude={"id"})))
                continue

            existing = existing_by_id.get(payment_in.id)
            if existing is None:
                raise BadRequestException(
                    f"Payment {payment_in.id} does not belong to this order"
                )
            for field in ("amount", "payment_method", "entry_type", "note"):
                new_value = getattr(payment_in, field)
                if getattr(existing, field) != new_value:
                    setattr(existing, field, new_value)
            merged.append(existing)

        return merged

    def _resolve_effective_dates(
        self, order: Order, order_in: OrderUpdate
    ) -> tuple[date, date]:
        """Resolve the start/end dates that should apply after the update."""
        start_time = order_in.start_time if order_in.start_time else order.start_time
        end_time = order_in.end_time if order_in.end_time else order.end_time
        return start_time, end_time

    def _build_items_from_links(self, order: Order) -> list[ItemVariantQuantity]:
        """Reconstruct the current item list from an order's existing links."""
        items = []
        for link in order.item_links:
            if link.item_variant is None:
                raise BadRequestException("Order has an invalid item variant link")
            items.append(
                ItemVariantQuantity(
                    item_id=link.item_variant.item_id,
                    item_variant_id=link.item_variant_id,
                    quantity=link.quantity,
                    price=link.price,
                    deposit=link.deposit,
                )
            )
        return items

    def _validate_updated_items(
        self,
        order: Order,
        order_in: OrderUpdate,
        start_time: date,
        end_time: date,
        existing_links: dict[UUID, OrderItemLink],
    ) -> None:
        """Re-validate item availability when items or dates changed."""
        items_to_validate = order_in.items
        dates_changed = start_time != order.start_time or end_time != order.end_time
        if items_to_validate is None and dates_changed:
            items_to_validate = self._build_items_from_links(order)

        if items_to_validate is None:
            return
        if not items_to_validate:
            raise BadRequestException("Order must contain items")

        # Closing an order (DONE/RETURNED) hands the item back rather than
        # booking it out, so maintenance/availability no longer applies.
        effective_status = (
            order_in.status if order_in.status is not None else order.status
        )
        if effective_status in (OrderStatus.DONE, OrderStatus.RETURNED):
            return

        self.validate_order_items(
            items=items_to_validate,
            start_time=start_time,
            end_time=end_time,
            exclude_order_id=order.id,
            existing_links=existing_links,
        )
