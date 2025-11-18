from uuid import UUID
from typing import List, Optional
from sqlmodel import Session, select
from datetime import datetime

from core.logger import logger
from models.item_variant import (ItemVariant, ItemVariantFilters,
                                 ItemVariantUpdate, ItemVariantStatus,
                                 ItemVariantCreate, ItemVariantPrice)
from models.links import OrderItemLink
from models.order import Order
from core.exceptions import NotFoundException, BadRequestException
from core.query_utils import apply_sorting
from core.database import get_total_count


class ItemVariantService:
    """Business logic for item variant operations"""

    def __init__(self, session: Session):
        self.session = session

    def _apply_filters(self, stmt, filters: ItemVariantFilters):
        """Apply filters to item variant query"""

        # Always exclude archived items by default
        stmt = stmt.where(ItemVariant.is_archived == False)

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
            stmt = stmt.where(
                ItemVariant.service_end_time == filters.service_end_time)
        if filters.service_start_time:
            stmt = stmt.where(
                ItemVariant.service_start_time == filters.service_start_time)

        return stmt.distinct()

    def get_variants(self,
                     filters: ItemVariantFilters,
                     offset: int = 0,
                     limit: int = 100,
                     sort_field: str = "id",
                     sort_order: str = "ASC") -> tuple[List[ItemVariant], int]:
        """Get filtered and paginated variants with total count"""
        logger.debug("Fetching variants")

        stmt = select(ItemVariant)
        stmt = self._apply_filters(stmt, filters)
        stmt = apply_sorting(stmt, ItemVariant, sort_field, sort_order)

        # Get total count before pagination
        total = get_total_count(self.session, stmt)

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)
        variants = self.session.exec(stmt).all()

        logger.debug(f"Found {len(variants)} variants out of {total} total")
        return variants, total

    def get_by_id(self, variant_id: UUID) -> Optional[ItemVariant]:
        logger.debug(f"Fetching variant by ID: {variant_id}")
        return self.session.get(ItemVariant, variant_id)

    def create(self, variant_in: ItemVariantCreate) -> ItemVariant:
        """Create a new item variant"""
        logger.debug(f"Creating new variant for item {variant_in.item_id}")

        # Extract variant data
        variant_data = variant_in.model_dump(exclude={"prices"})

        # Create prices separately
        prices = []
        if hasattr(variant_in, 'prices') and variant_in.prices:
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
            logger.info(f"Variant {variant.id} has linked orders. "
                        "Archiving instead of deleting")

            variant.is_archived = True
            self.session.add(variant)
            self.session.commit()
            logger.info(f"Variant {variant.id} archived successfully")
            return

        # No orders - safe to delete
        self.session.delete(variant)
        self.session.commit()
        logger.info(f"Variant {variant.id} deleted successfully")

    def update(self, variant: ItemVariant,
               variant_in: ItemVariantUpdate) -> ItemVariant:
        """Update existing item variant and its prices"""
        logger.debug(f"Updating variant: {variant.id}")

        # # Extract update data
        update_data = variant_in.model_dump(exclude={"prices"},
                                            exclude_unset=True)

        # Update variant fields
        for field, value in update_data.items():
            setattr(variant, field, value)

        # Update prices if provided
        if variant_in.prices is not None:
            variant.prices = [
                ItemVariantPrice(**p.model_dump()) for p in variant_in.prices
            ]

        # Clear service dates if status is set to available
        if variant.status == ItemVariantStatus.AVAILABLE:
            variant.service_start_time = None
            variant.service_end_time = None

        self.session.add(variant)
        self.session.commit()
        self.session.refresh(variant)

        logger.info(f"Variant updated successfully: {variant.id}")
        return variant

    def get_by_item_id(self, item_id: UUID) -> List[ItemVariant]:
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
            ItemVariant.status == ItemVariantStatus.AVAILABLE)
        variants = self.session.exec(stmt).all()
        return len(variants)

    def get_variants_by_status(self,
                               status: ItemVariantStatus) -> List[ItemVariant]:
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
            exclude_order_id: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """Validate item variant availability for the given time period"""

        # Check if variant is archived
        if variant.is_archived and exclude_order_id == None:
            return False, f"Variant {variant.id} is archived"

        # Check service availability (maintenance periods)
        if variant.service_end_time and variant.service_end_time > start_time:
            return False, f"Variant {variant.id} under maintenance until {variant.service_end_time}"

        # Check for booking conflicts
        stmt = select(OrderItemLink.order_id).join(Order)
        stmt = stmt.where(
            OrderItemLink.item_variant_id == variant.id,
            Order.status.in_(["booked", "issued"]),
            Order.is_archived == False,
            Order.start_time <= end_time,
            Order.end_time >= start_time,
        )
        # Exclude current order when updating
        if exclude_order_id:
            stmt = stmt.where(Order.id != exclude_order_id)
        order_id = self.session.exec(stmt).first()
        if order_id:
            return False, f"Variant {variant.id} already booked during this period by {order_id}"

        return True, None
