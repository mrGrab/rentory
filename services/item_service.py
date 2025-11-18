from uuid import UUID
from datetime import datetime, timezone, date
from typing import List, Optional
from sqlmodel import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy import text

# --- Project Imports ---
from core.query_utils import apply_sorting
from core.database import get_total_count, SessionDep
from core.logger import logger
from core.exceptions import ConflictException, BadRequestException
from services.item_variant_service import ItemVariantService
from models.order import Order
from models.links import OrderItemLink
from models.item import Item, ItemCreate, ItemUpdate, ItemFilters
from models.item_variant import ItemVariantCreate, ItemVariantStatus, ItemVariant


class ItemService:
    """Handles all business logic and database operations for Items"""

    def __init__(self, session: SessionDep):
        self.session = session
        self.variant_service = ItemVariantService(session)

    def _apply_filters(self, stmt, filters: ItemFilters):
        """Applies all filters to the item query statement"""

        # Always exclude archived items by default
        stmt = stmt.where(Item.is_archived == False)

        # Join ItemVariant if any variant-specific filters are present
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

    def get_items(self,
                  filters: ItemFilters,
                  offset: int = 0,
                  limit: int = 100,
                  sort_field: str = "id",
                  sort_order: str = "DESC") -> tuple[List[Item], int]:
        """
        Get filtered and paginated items with total count

        Args:
            filters: Filter criteria for items
            offset: Number of records to skip
            limit: Maximum number of records to return
            sort_field: Field to sort by
            sort_order: Sort direction (ASC or DESC)

        Returns:
            Tuple of (list of items, total count)
        """
        logger.debug(f"Fetching items with filters")

        stmt = select(Item)
        stmt = self._apply_filters(stmt, filters)
        stmt = apply_sorting(stmt, Item, sort_field, sort_order)

        # Get total count before pagination
        total = get_total_count(self.session, stmt)

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)
        items = self.session.exec(stmt).all()

        logger.debug(f"Found {len(items)} items out of {total} total")
        return items, total

    def get_by_id(self, item_id: UUID) -> Optional[Item]:
        """
        Get item by ID

        Args:
            item_id: Item UUID

        Returns:
            Item or None if not found
        """
        logger.debug(f"Fetching item by ID: {item_id}")
        return self.session.get(Item, item_id)

    def create(self, item_in: ItemCreate) -> Item:
        """
        Create a new item with variants

        Args:
            item_in: Item creation data

        Returns:
            Created item

        Raises:
            ConflictException: If title already exists
        """
        logger.debug(f"Creating item with title: {item_in.title}")

        # Check for duplicate title
        stmt = select(Item.id).where(Item.title == item_in.title)
        existing = self.session.exec(stmt).first()
        if existing:
            logger.warning(f"Item with title '{item_in.title}' already exists")
            raise ConflictException(f"Item with this title already exists")

        # Create item
        item_data = item_in.model_dump(exclude={"variants"})
        item = Item(**item_data)
        self.session.add(item)
        self.session.flush()

        # Create variants if provided
        if item_in.variants:
            for variant_in in item_in.variants:
                variant_create = ItemVariantCreate(**variant_in.model_dump(),
                                                   item_id=item.id)
                self.variant_service.create(variant_create)

        self.session.commit()
        self.session.refresh(item)

        logger.info(f"Item created successfully: {item.id}")
        return item

    def update(self, item: Item, item_in: ItemUpdate) -> Item:
        """
        Update existing item

        Args:
            item: Existing item instance
            item_in: Update data

        Returns:
            Updated item

        Raises:
            BadRequestException: If no data provided for update
            ConflictException: If title already exists for another item
        """
        logger.debug(f"Updating item: {item.id}")

        update_data = item_in.model_dump(exclude={"variants"},
                                         exclude_unset=True)

        if not update_data and not item_in.variants:
            logger.warning("No data provided for update")
            raise BadRequestException("No data provided for update")

        # Check if title is being updated and if it already exists
        title = update_data.get("title", None)
        if title and title != item.title:
            stmt = select(Item.id)
            stmt = stmt.where(Item.title == title, Item.id != item.id)
            existing = self.session.exec(stmt).first()
            if existing:
                logger.warning(f"Title '{title}' already exists")
                raise ConflictException(f"Title '{title}' is already in use")

        # Update item fields
        for field, value in update_data.items():
            setattr(item, field, value)

        existing_variants_map = {v.id: v for v in item.variants}
        processed_variant_ids = set()

        for variant_in in item_in.variants:

            # New variant (no ID)
            if not hasattr(variant_in, 'id') or not variant_in.id:
                variant_create = ItemVariantCreate(
                    item_id=item.id,
                    **variant_in.model_dump(exclude_unset=True))
                self.variant_service.create(variant_create)
                continue

            # Update existing variant
            if variant_in.id in existing_variants_map:
                existing_variant = existing_variants_map[variant_in.id]
                processed_variant_ids.add(existing_variant.id)
                # Update in place
                self.variant_service.update(existing_variant, variant_in)
            else:
                logger.warning(f"Variant {variant_in.id} not found, skipping")

        # Delete variants not in the update list
        to_delete = set(existing_variants_map.keys()) - processed_variant_ids
        for variant_id in to_delete:
            logger.debug(f"Deleting variant {variant_id} (not in update list)")
            self.variant_service.delete(existing_variants_map[variant_id])

        item.updated_at = datetime.now(timezone.utc)

        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)

        logger.info(f"Item updated successfully: {item.id}")
        return item

    def delete(self, item: Item) -> None:
        """
        Delete item if no active orders exist or archive

        Args:
            item: Item to delete
        """
        logger.debug(f"Attempting to delete item: {item.id}")

        # Check for active orders
        for variant in item.variants:
            if variant.order_links:
                item.is_archived = True
                item.updated_at = datetime.now(timezone.utc)

                self.session.add(item)
                self.session.commit()

                logger.info(f"Order {item.id} archived successfully")
                return

        # Safe to delete
        self.session.delete(item)
        self.session.commit()

        logger.info(f"Item deleted successfully: {item.id}")

    def check_availability(self,
                           item: Item,
                           start_time,
                           end_time,
                           exclude_order_id: Optional[int] = None) -> Item:
        """Check item variant availability for a time period"""
        if start_time > end_time:
            raise BadRequestException("Start time must be before end time")

        logger.debug(f"Checking availability for item {item.id} "
                     f"from {start_time} to {end_time}")

        # Update variant availability status
        for variant in item.variants:
            is_available, reason = self.variant_service.check_availability(
                variant, start_time, end_time, exclude_order_id)

            if not is_available:
                logger.debug(reason)
                variant.status = ItemVariantStatus.UNAVAILABLE

        logger.info(f"Availability checked for item {item.id}")
        return item

    def get_distinct_field_values(self, model: type,
                                  field_name: str) -> List[str]:
        """
        Get distinct values for a field (for dropdown options)

        Args:
            model: SQLModel class (Item or ItemVariant)
            field_name: Name of the field

        Returns:
            Sorted list of distinct values
        """
        logger.debug(
            f"Fetching distinct {field_name} values from {model.__name__}")

        field_attr = getattr(model, field_name)
        stmt = select(field_attr).where(field_attr.is_not(None)).distinct()
        results = self.session.exec(stmt).all()

        # Filter out None and convert to strings
        filtered_results = [result for result in results if result is not None]

        logger.debug(
            f"Retrieved {len(filtered_results)} distinct {field_name} values")
        return sorted(filtered_results)
