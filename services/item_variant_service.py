from datetime import datetime
from uuid import UUID

from sqlmodel import Session, func, select

from core.exceptions import BadRequestException
from core.logger import logger
from core.query_gateway import QueryGateway
from models.item_variant import (
    ItemVariant,
    ItemVariantCreate,
    ItemVariantFilters,
    ItemVariantPrice,
    ItemVariantStatus,
    ItemVariantUpdate,
)
from models.links import OrderItemLink
from models.order import Order, OrderStatus
from services.item_variant_query_gateway import ItemVariantQueryGateway


class ItemVariantService:
    """Business logic for item variant operations"""

    def __init__(self, session: Session):
        self.session = session
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

    def create(self, variant_in: ItemVariantCreate) -> ItemVariant:
        """Create a new item variant"""
        logger.debug(f"Creating new variant for item {variant_in.item_id}")

        if variant_in.quantity_in_maintenance > variant_in.quantity:
            raise BadRequestException("quantity_in_maintenance cannot exceed quantity")

        # Extract variant data
        variant_data = variant_in.model_dump(exclude={"prices"})

        # Create prices separately
        prices = []
        if hasattr(variant_in, "prices") and variant_in.prices:
            prices = [
                ItemVariantPrice(**p.model_dump(exclude={"id"}))
                for p in variant_in.prices
            ]

        # Create variant with prices
        variant = ItemVariant(**variant_data, prices=prices)

        self.session.add(variant)
        self.session.commit()
        self.session.refresh(variant)

        logger.info(f"Item variant created successfully: {variant.id}")
        return variant

    def delete(self, variant: ItemVariant) -> None:
        """Delete variant or archive if it has orders"""
        logger.debug(f"Attempting to delete variant: {variant.id}")

        if variant.order_links and len(variant.order_links) > 0:
            logger.info(
                f"Variant {variant.id} has linked orders. Archiving instead of deleting"
            )

            variant.is_archived = True
            self.session.add(variant)
            self.session.commit()
            logger.info(f"Variant {variant.id} archived successfully")
            return

        # No orders - safe to delete
        self.session.delete(variant)
        self.session.commit()
        logger.info(f"Variant {variant.id} deleted successfully")

    def update(
        self, variant: ItemVariant, variant_in: ItemVariantUpdate
    ) -> ItemVariant:
        """Update existing item variant and its prices"""
        logger.debug(f"Updating variant: {variant.id}")

        # # Extract update data
        update_data = variant_in.model_dump(exclude={"prices"}, exclude_unset=True)

        new_quantity = update_data.get("quantity", variant.quantity)
        new_quantity_in_maintenance = update_data.get(
            "quantity_in_maintenance", variant.quantity_in_maintenance
        )
        if new_quantity_in_maintenance > new_quantity:
            raise BadRequestException("quantity_in_maintenance cannot exceed quantity")

        # Update variant fields
        for field, value in update_data.items():
            setattr(variant, field, value)

        # Update prices if provided
        if variant_in.prices is not None:
            variant.prices = [
                ItemVariantPrice(**p.model_dump()) for p in variant_in.prices
            ]

        # Clear service dates and maintenance count if status is set to available
        if variant.status == ItemVariantStatus.AVAILABLE:
            variant.service_start_time = None
            variant.service_end_time = None
            variant.quantity_in_maintenance = 0

        self.session.add(variant)
        self.session.commit()
        self.session.refresh(variant)

        logger.info(f"Variant updated successfully: {variant.id}")
        return variant

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
        return variants

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
        return variants

    def check_availability(
        self,
        variant: ItemVariant,
        start_time: datetime,
        end_time: datetime,
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
            if isinstance(service_end_date, datetime):
                service_end_date = service_end_date.date()

            start_date = (
                start_time.date() if isinstance(start_time, datetime) else start_time
            )

            if service_end_date >= start_date:
                effective_quantity -= variant.quantity_in_maintenance

        # Sum booked quantities across all overlapping active orders
        stmt = select(func.coalesce(func.sum(OrderItemLink.quantity), 0)).join(Order)
        stmt = stmt.where(
            OrderItemLink.item_variant_id == variant.id,
            Order.status.in_(
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
