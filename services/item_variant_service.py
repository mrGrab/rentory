from datetime import date, datetime
from uuid import UUID

from sqlalchemy import inspect
from sqlmodel import Session, func, select

from core.exceptions import BadRequestException
from core.logger import logger
from core.query_gateway import QueryGateway
from models.item_variant import (
    ItemVariant,
    ItemVariantCreate,
    ItemVariantFilters,
    ItemVariantPrice,
    ItemVariantPriceBase,
    ItemVariantStatus,
    ItemVariantUpdate,
)
from models.links import OrderItemLink
from models.order import Order, OrderStatus
from services.item_variant_query_gateway import ItemVariantQueryGateway


class ItemVariantService:
    """Business logic for item variant operations"""

    def __init__(self, session: Session):
        self.session: Session = session
        self.query_gateway: QueryGateway[ItemVariant, ItemVariantFilters] = (
            ItemVariantQueryGateway(session)
        )

    def get_by_id(self, variant_id: UUID) -> ItemVariant | None:
        logger.debug(f"Fetching variant by ID: {variant_id}")
        return self.query_gateway.get_by_id(variant_id)

    def get_variants(
        self,
        filters: ItemVariantFilters,
        offset: int = 0,
        limit: int = 100,
        sort_field: str = "id",
        sort_order: str = "ASC",
    ) -> tuple[list[ItemVariant], int]:
        """Get filtered and paginated variants with total count"""
        logger.debug("Fetching variants")
        variants, total = self.query_gateway.list(
            filters=filters,
            offset=offset,
            limit=limit,
            sort_field=sort_field,
            sort_order=sort_order,
        )

        logger.debug(f"Found {len(variants)} variants out of {total} total")
        return variants, total

    def create(
        self, variant_in: ItemVariantCreate, *, commit: bool = True
    ) -> ItemVariant:
        """Create a new item variant"""
        logger.debug(f"Creating new variant for item {variant_in.item_id}")

        if variant_in.quantity_in_maintenance > variant_in.quantity:
            raise BadRequestException("quantity_in_maintenance cannot exceed quantity")

        self._validate_variant_identity(
            item_id=variant_in.item_id,
            size=variant_in.size,
            color=variant_in.color,
        )

        # New variants are always active; size_key/color_key mirror the
        # normalized identity used for the uniqueness constraint.
        variant = ItemVariant(
            item_id=variant_in.item_id,
            size=variant_in.size,
            color=variant_in.color,
            image_url=variant_in.image_url,
            status=variant_in.status,
            quantity=variant_in.quantity,
            quantity_in_maintenance=variant_in.quantity_in_maintenance,
            service_start_time=variant_in.service_start_time,
            service_end_time=variant_in.service_end_time,
            size_key=self.normalize_identity(variant_in.size),
            color_key=self.normalize_identity(variant_in.color),
            active_identity_key="active",
        )
        # `id` is populated eagerly via UUIDMixin's default_factory, so it's
        # available before the variant is flushed to the database.
        if variant.id is None:
            raise BadRequestException("Variant creation did not produce an ID")

        variant.prices = [
            ItemVariantPrice(
                variant_id=variant.id,
                amount=p.amount,
                deposit=p.deposit or 0,
                price_type=p.price_type,
            )
            for p in variant_in.prices
        ]

        self.session.add(variant)
        if commit:
            self.session.commit()
            self.session.refresh(variant)
        else:
            self.session.flush()

        logger.info(f"Item variant created successfully: {variant.id}")
        return variant

    def delete(self, variant: ItemVariant, *, commit: bool = True) -> None:
        """Delete variant or archive if it has orders"""
        logger.debug(f"Attempting to delete variant: {variant.id}")

        if variant.order_links and len(variant.order_links) > 0:
            logger.info(
                f"Variant {variant.id} has linked orders. Archiving instead of deleting"
            )

            variant.is_archived = True
            variant.active_identity_key = None
            self.session.add(variant)
            if commit:
                self.session.commit()
            else:
                self.session.flush()
            logger.info(f"Variant {variant.id} archived successfully")
            return

        # No orders - safe to delete
        self.session.delete(variant)
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        logger.info(f"Variant {variant.id} deleted successfully")

    def update(
        self,
        variant: ItemVariant,
        variant_in: ItemVariantUpdate,
        *,
        commit: bool = True,
    ) -> ItemVariant:
        """Update existing item variant and its prices"""
        logger.debug(f"Updating variant: {variant.id}")
        if variant.id is None:
            raise BadRequestException(
                "Variant must have an ID before it can be updated"
            )

        # Extract update data
        update_data = variant_in.model_dump(
            exclude={"id", "prices"}, exclude_unset=True
        )

        new_quantity = (
            variant_in.quantity if variant_in.quantity is not None else variant.quantity
        )
        new_quantity_in_maintenance = (
            variant_in.quantity_in_maintenance
            if variant_in.quantity_in_maintenance is not None
            else variant.quantity_in_maintenance
        )
        if new_quantity_in_maintenance > new_quantity:
            raise BadRequestException("quantity_in_maintenance cannot exceed quantity")
        if new_quantity < self._maximum_reserved_quantity(variant.id):
            raise BadRequestException(
                "quantity cannot be lower than the maximum concurrently reserved quantity"
            )

        new_is_archived = (
            variant_in.is_archived
            if variant_in.is_archived is not None
            else variant.is_archived
        )
        new_size = variant_in.size if "size" in update_data else variant.size
        new_color = variant_in.color if "color" in update_data else variant.color
        if not new_is_archived:
            self._validate_variant_identity(
                item_id=variant.item_id,
                size=new_size,
                color=new_color,
                exclude_variant_id=variant.id,
            )
        update_data.update(
            self._identity_values(new_size, new_color, is_archived=new_is_archived)
        )

        # Update variant fields
        for field, value in update_data.items():
            setattr(variant, field, value)

        # Update prices if provided
        if variant_in.prices is not None:
            self._update_prices(variant, variant_in.prices)

        # Clear service dates and maintenance count if status is set to available
        if variant.status == ItemVariantStatus.AVAILABLE:
            variant.service_start_time = None
            variant.service_end_time = None
            variant.quantity_in_maintenance = 0

        self.session.add(variant)
        if commit:
            self.session.commit()
            self.session.refresh(variant)
        else:
            self.session.flush()

        logger.info(f"Variant updated successfully: {variant.id}")
        return variant

    @staticmethod
    def normalize_identity(value: str | None) -> str:
        return value.strip().casefold() if value and value.strip() else ""

    def _identity_values(
        self, size: str | None, color: str | None, is_archived: bool = False
    ) -> dict[str, str | None]:
        return {
            "size_key": self.normalize_identity(size),
            "color_key": self.normalize_identity(color),
            "active_identity_key": None if is_archived else "active",
        }

    def _validate_variant_identity(
        self,
        item_id: UUID,
        size: str | None,
        color: str | None,
        exclude_variant_id: UUID | None = None,
    ) -> None:
        stmt = select(ItemVariant.id).where(
            ItemVariant.item_id == item_id,
            ItemVariant.size_key == self.normalize_identity(size),
            ItemVariant.color_key == self.normalize_identity(color),
            ItemVariant.is_archived == False,
        )
        if exclude_variant_id is not None:
            stmt = stmt.where(ItemVariant.id != exclude_variant_id)
        if self.session.exec(stmt).first() is not None:
            raise BadRequestException(
                "An active variant with this size and color already exists for the item"
            )

    def _update_prices(
        self, variant: ItemVariant, prices: list[ItemVariantPriceBase]
    ) -> None:
        price_type_keys = [
            self.normalize_identity(price.price_type)
            for price in prices
            if price.price_type
        ]
        if len(price_type_keys) != len(set(price_type_keys)):
            raise BadRequestException("Price tier names must be unique per variant")

        existing_prices = {price.id: price for price in variant.prices}
        updated_prices: list[ItemVariantPrice] = []
        for price_in in prices:
            if price_in.id is not None:
                existing_price = existing_prices.get(price_in.id)
                if existing_price is None:
                    raise BadRequestException(
                        f"Price tier {price_in.id} does not belong to variant {variant.id}"
                    )
                existing_price.amount = price_in.amount
                existing_price.deposit = price_in.deposit or 0
                existing_price.price_type = price_in.price_type
                updated_prices.append(existing_price)
            else:
                if variant.id is None:
                    raise BadRequestException(
                        "Variant must have an ID before adding prices"
                    )
                updated_prices.append(
                    ItemVariantPrice(
                        variant_id=variant.id,
                        amount=price_in.amount,
                        deposit=price_in.deposit or 0,
                        price_type=price_in.price_type,
                    )
                )
        variant.prices = updated_prices

    def _maximum_reserved_quantity(self, variant_id: UUID) -> int:
        active_statuses = {
            OrderStatus.BOOKED,
            OrderStatus.BOOKED_NOT_PAID,
            OrderStatus.ISSUED,
        }
        stmt = (
            select(Order)
            .join(OrderItemLink)
            .where(
                OrderItemLink.item_variant_id == variant_id,
                Order.is_archived == False,
            )
        )
        events: dict[date, int] = {}
        for order in self.session.exec(stmt).all():
            if order.status not in active_statuses:
                continue
            link = next(
                link for link in order.item_links if link.item_variant_id == variant_id
            )
            events[order.start_time] = events.get(order.start_time, 0) + link.quantity
            end_after = date.fromordinal(order.end_time.toordinal() + 1)
            events[end_after] = events.get(end_after, 0) - link.quantity

        reserved = maximum = 0
        for event_date in sorted(events):
            reserved += events[event_date]
            maximum = max(maximum, reserved)
        return maximum

    def get_by_item_id(self, item_id: UUID) -> list[ItemVariant]:
        """
        Get all variants for a specific item

        Args:
            item_id: Item UUID

        Returns:
            List of variants belonging to the item
        """
        logger.debug(f"Fetching variants for item: {item_id}")

        stmt = select(ItemVariant).where(ItemVariant.item_id == item_id)
        variants = self.session.exec(stmt).all()

        logger.debug(f"Found {len(variants)} variants for item {item_id}")
        return list(variants)

    def count_available_variants(self, item_id: UUID) -> int:
        """
        Count available variants for an item

        Args:
            item_id: Item UUID

        Returns:
            Number of available variants
        """
        stmt = select(ItemVariant).where(
            ItemVariant.item_id == item_id,
            ItemVariant.status == ItemVariantStatus.AVAILABLE,
        )
        variants = self.session.exec(stmt).all()
        return len(variants)

    def get_variants_by_status(self, status: ItemVariantStatus) -> list[ItemVariant]:
        """
        Get all variants with a specific status

        Args:
            status: Variant status to filter by

        Returns:
            List of variants with the specified status
        """
        logger.debug(f"Fetching variants with status: {status}")

        stmt = select(ItemVariant).where(ItemVariant.status == status)
        variants = self.session.exec(stmt).all()

        logger.debug(f"Found {len(variants)} variants with status {status}")
        return list(variants)

    def check_availability(
        self,
        variant: ItemVariant,
        start_time: date,
        end_time: date,
        exclude_order_id: int | None = None,
    ) -> tuple[bool, int, str | None]:
        """Validate item variant availability for the given time period.

        Returns (is_available, available_quantity, reason).
        """

        # Check if variant is archived
        if variant.is_archived and exclude_order_id == None:
            return False, 0, f"Variant {variant.id} is archived"

        # Units of the variant's quantity that maintenance takes out of the pool
        effective_quantity = variant.quantity
        if variant.service_end_time and variant.status != ItemVariantStatus.CLEANING:
            service_end_date = variant.service_end_time
            start_date = (
                start_time.date() if isinstance(start_time, datetime) else start_time
            )
            if service_end_date >= start_date:
                effective_quantity -= variant.quantity_in_maintenance

        # Sum booked quantities across all overlapping active orders
        stmt = select(func.coalesce(func.sum(OrderItemLink.quantity), 0)).join(Order)
        stmt = stmt.where(
            OrderItemLink.item_variant_id == variant.id,
            inspect(Order)
            .columns["status"]
            .in_(
                [
                    OrderStatus.BOOKED,
                    OrderStatus.BOOKED_NOT_PAID,
                    OrderStatus.ISSUED,
                ]
            ),
            Order.is_archived == False,
            Order.start_time <= end_time,
            Order.end_time >= start_time,
        )
        # Exclude current order when updating
        if exclude_order_id:
            stmt = stmt.where(Order.id != exclude_order_id)
        booked_quantity = self.session.exec(stmt).one()

        available_quantity = effective_quantity - booked_quantity
        if available_quantity <= 0:
            return (
                False,
                max(available_quantity, 0),
                (
                    f"Variant {variant.id} is fully booked or under maintenance during "
                    f"this period ({booked_quantity} booked, "
                    f"{variant.quantity_in_maintenance} in maintenance, "
                    f"{variant.quantity} total)"
                ),
            )

        return True, available_quantity, None
