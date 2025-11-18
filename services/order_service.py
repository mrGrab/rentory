from uuid import UUID
from datetime import datetime, timezone, date
from typing import List, Optional
from sqlmodel import select, func

# --- Project Imports ---
from core.logger import logger
from core.query_utils import apply_sorting
from core.database import get_total_count
from core.exceptions import ConflictException, BadRequestException
from models.client import Client
from models.payment import Payment
from models.item_variant import ItemVariant
from models.links import OrderItemLink
from models.order import Order, OrderCreate, OrderUpdate, OrderFilters


class OrderService:
    """Business logic for order operations"""

    def __init__(self, session):
        self.session = session

    def _apply_filters(self, stmt, filters: OrderFilters):
        """Apply filters to order query"""

        # By default, exclude archived orders
        if filters.is_archived is not None:
            stmt = stmt.where(Order.is_archived == filters.is_archived)
        else:
            stmt = stmt.where(Order.is_archived == False)

        # Phone filter (requires join with Client)
        if filters.phone:
            stmt = stmt.join(Client)
            stmt = stmt.where(Client.phone.ilike(f"%{filters.phone}%"))

        # Order ID filter
        if filters.id:
            if isinstance(filters.id, list):
                stmt = stmt.where(Order.id.in_(filters.id))
            else:
                stmt = stmt.where(Order.id == filters.id)

        # Client ID filter
        if filters.client_id:
            stmt = stmt.where(Order.client_id == filters.client_id)

        # Time range filters (handle overlapping ranges)
        if filters.start_time and filters.end_time:
            # Find orders that overlap with the filter time range
            stmt = stmt.where(Order.end_time >= filters.start_time,
                              Order.start_time <= filters.end_time)
        elif filters.end_time:
            stmt = stmt.where(Order.end_time == filters.end_time)
        elif filters.start_time:
            stmt = stmt.where(Order.start_time == filters.start_time)

        # Tag filter
        if filters.tag:
            stmt = stmt.where(Order.tags.contains([filters.tag]))

        # Status filter
        if filters.status:
            stmt = stmt.where(Order.status == filters.status)

        # Item IDs filter (requires joins)
        if filters.item_ids:
            stmt = stmt.join(Order.item_links).join(OrderItemLink.item_variant)
            stmt = stmt.where(ItemVariant.item_id.in_(filters.item_ids))

        # Pickup type filter (JSON field query)
        if filters.pickup_type:
            stmt = stmt.where(
                Order.delivery_info["pickup_type"] == filters.pickup_type)

        # Created date
        if filters.created_at:
            stmt = stmt.where(
                func.date(Order.created_at) == filters.created_at.date())

        return stmt.distinct()

    def get_orders(self,
                   filters: OrderFilters,
                   offset: int = 0,
                   limit: int = 100,
                   sort_field: str = "created_at",
                   sort_order: str = "DESC") -> tuple[List[Order], int]:
        """Get filtered and paginated orders with total count"""
        logger.debug(f"Fetching orders")

        stmt = select(Order)
        stmt = self._apply_filters(stmt, filters)
        stmt = apply_sorting(stmt, Order, sort_field, sort_order)

        # Get total count before pagination
        total = get_total_count(self.session, stmt)

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)
        orders = self.session.exec(stmt).all()

        logger.debug(f"Found {len(orders)} orders out of {total} total")
        return orders, total

    def get_by_id(self, order_id: int) -> Optional[Order]:
        """Get order by ID"""
        logger.debug(f"Fetching order by ID: {order_id}")
        return self.session.get(Order, order_id)

    def check_variant_availability(
            self,
            variant_id: UUID,
            start_time: date,
            end_time: date,
            exclude_order_id: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """Check if variant is available for booking period"""
        # Get variant
        variant: ItemVariant = self.session.get(ItemVariant, variant_id)
        if not variant:
            return False, f"Variant {variant_id} not found"

        # Check if variant is archived
        if variant.is_archived and exclude_order_id == None:
            return False, f"Variant {variant_id} is archived"

        # Check service availability (maintenance periods)
        if variant.service_end_time and variant.service_end_time > start_time:
            return False, f"Variant {variant_id} under maintenance until {variant.service_end_time}"

        # Check for booking conflicts
        stmt = select(OrderItemLink.item_variant_id).join(Order)
        stmt = stmt.where(
            OrderItemLink.item_variant_id == variant_id,
            Order.status.in_(["booked", "issued"]),
            Order.is_archived == False,
            Order.start_time <= end_time,
            Order.end_time >= start_time,
        )

        # Exclude current order when updating
        if exclude_order_id:
            stmt = stmt.where(Order.id != exclude_order_id)

        if self.session.exec(stmt).first():
            return False, f"Variant {variant_id} already booked during this period"

        return True, None

    def validate_order_items(self,
                             items: List,
                             start_time: date,
                             end_time: date,
                             exclude_order_id: Optional[int] = None) -> None:
        """Validate all items in order are available"""
        if not items:
            raise BadRequestException("Order must contain at least one item")

        unavailable_variants = []

        for item in items:
            is_available, reason = self.check_variant_availability(
                variant_id=item.item_variant_id,
                start_time=start_time,
                end_time=end_time,
                exclude_order_id=exclude_order_id)

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
        if order_in.start_time >= order_in.end_time:
            raise BadRequestException("Start time must be before end time")

        # Validate item availability
        self.validate_order_items(items=order_in.items,
                                  start_time=order_in.start_time,
                                  end_time=order_in.end_time)

        # Create the order
        order_data = order_in.model_dump(exclude={"items", "payments"},
                                         exclude_unset=True)
        order = Order(**order_data)

        # Create order-item links
        order.item_links = [
            OrderItemLink(
                item_variant_id=item.item_variant_id,
                price=item.price,
                deposit=item.deposit,
                quantity=item.quantity,
            ) for item in order_in.items
        ]

        # Create payments if provided
        if order_in.payments:
            order.payments = [
                Payment(**payment.model_dump())
                for payment in order_in.payments
            ]

        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)

        logger.info(f"Order {order.id} created successfully")
        return order

    def update(self, order: Order, order_in: OrderUpdate) -> Order:
        """Update existing order"""
        logger.debug(f"Updating order: {order.id}")

        update_data = order_in.model_dump(exclude={"items", "payments"},
                                          exclude_unset=True)

        if not update_data and not order_in.items and not order_in.payments:
            logger.warning("No data provided for update")
            raise BadRequestException("No data provided for update")

        # Get effective dates for validation
        start_time = order_in.start_time if order_in.start_time else order.start_time
        end_time = order_in.end_time if order_in.end_time else order.end_time

        # Validate dates
        if start_time >= end_time:
            raise BadRequestException("Start time must be before end time")

        # Validate items if provided
        if order_in.items is not None:
            if not order_in.items:
                raise BadRequestException("Order must contain items")

            self.validate_order_items(items=order_in.items,
                                      start_time=start_time,
                                      end_time=end_time,
                                      exclude_order_id=order.id)

        # Update order fields
        for field, value in update_data.items():
            setattr(order, field, value)

        # Update items if provided
        if order_in.items is not None:
            order.item_links = [
                OrderItemLink(
                    item_variant_id=item.item_variant_id,
                    price=item.price,
                    deposit=item.deposit,
                    quantity=item.quantity,
                ) for item in order_in.items
            ]

        # Update payments if provided
        if order_in.payments is not None:
            order.payments = [
                Payment(**payment.model_dump())
                for payment in order_in.payments
            ]

        order.updated_at = datetime.now(timezone.utc)
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)

        logger.info(f"Order {order.id} updated successfully")
        return order

    def archive(self, order: Order) -> None:
        """Archive an order (soft delete)"""
        logger.debug(f"Archiving order: {order.id}")

        order.is_archived = True
        order.updated_at = datetime.now(timezone.utc)

        self.session.add(order)
        self.session.commit()

        logger.info(f"Order {order.id} archived successfully")

    def delete(self, order: Order) -> None:
        """Delete an order"""

        logger.debug(f"Deleting order: {order.id}")

        self.session.delete(order)
        self.session.commit()

        logger.info(f"Order {order.id} deleted successfully")

    def get_orders_by_client(self, client_id: UUID) -> List[Order]:
        """Get all orders for a specific client"""
        logger.debug(f"Fetching orders for client: {client_id}")

        stmt = select(Order).where(Order.client_id == client_id)
        orders = self.session.exec(stmt).all()

        logger.debug(f"Found {len(orders)} orders for client {client_id}")
        return orders

    def get_orders_by_status(self, status: str) -> List[Order]:
        """Get all orders with a specific status"""
        logger.debug(f"Fetching orders with status: {status}")

        stmt = select(Order).where(Order.status == status)
        orders = self.session.exec(stmt).all()

        logger.debug(f"Found {len(orders)} orders with status {status}")
        return orders
