from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import select

# --- Project Imports ---
from core.database import SessionDep
from core.exceptions import BadRequestException, ConflictException
from core.logger import logger
from core.query_gateway import QueryGateway
from models.item import Item, ItemCreate, ItemFilters, ItemUpdate
from models.item_variant import ItemVariantCreate, ItemVariantStatus
from services.item_query_gateway import ItemQueryGateway
from services.item_variant_service import ItemVariantService


class ItemService:
    """Handles all business logic and database operations for Items"""

    def __init__(self, session: SessionDep):
        self.session = session
        self.variant_service = ItemVariantService(session)
        self.query_gateway: QueryGateway[Item, ItemFilters] = ItemQueryGateway(session)

    def get_items(
        self,
        filters: ItemFilters,
        offset: int = 0,
        limit: int = 100,
        sort_field: str = "id",
        sort_order: str = "DESC",
    ) -> tuple[list[Item], int]:
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
        logger.debug("Fetching items with filters")
        items, total = self.query_gateway.list(
            filters=filters,
            offset=offset,
            limit=limit,
            sort_field=sort_field,
            sort_order=sort_order,
        )

        logger.debug(f"Found {len(items)} items out of {total} total")
        return items, total

    def get_by_id(self, item_id: UUID) -> Item | None:
        """
        Get item by ID

        Args:
            item_id: Item UUID

        Returns:
            Item or None if not found
        """
        logger.debug(f"Fetching item by ID: {item_id}")
        return self.query_gateway.get_by_id(item_id)

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
            raise ConflictException("Item with this title already exists")

        # Create item
        item_data = item_in.model_dump(exclude={"variants"})
        item = Item(**item_data)
        self.session.add(item)
        self.session.flush()

        # Create variants if provided
        if item_in.variants:
            for variant_in in item_in.variants:
                variant_create = ItemVariantCreate(
                    **variant_in.model_dump(), item_id=item.id
                )
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

        update_data = item_in.model_dump(exclude={"variants"}, exclude_unset=True)

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
            if not hasattr(variant_in, "id") or not variant_in.id:
                variant_create = ItemVariantCreate(
                    item_id=item.id, **variant_in.model_dump(exclude_unset=True)
                )
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

        item.updated_at = datetime.now(UTC)

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
                item.updated_at = datetime.now(UTC)

                self.session.add(item)
                self.session.commit()

                logger.info(f"Order {item.id} archived successfully")
                return

        # Safe to delete
        self.session.delete(item)
        self.session.commit()

        logger.info(f"Item deleted successfully: {item.id}")

    def check_availability(
        self, item: Item, start_time, end_time, exclude_order_id: int | None = None
    ) -> tuple[Item, dict[UUID, int]]:
        """Check item variant availability for a time period.

        Returns (item, availability) where availability maps variant id to
        available_quantity, since that value isn't a persisted model field.
        """
        if start_time > end_time:
            raise BadRequestException("Start time must be before end time")

        logger.debug(
            f"Checking availability for item {item.id} from {start_time} to {end_time}"
        )

        # Update variant availability status
        availability: dict[UUID, int] = {}
        for variant in item.variants:
            is_available, available_quantity, reason = (
                self.variant_service.check_availability(
                    variant, start_time, end_time, exclude_order_id
                )
            )

            availability[variant.id] = available_quantity

            if not is_available:
                logger.debug(reason)
                variant.status = ItemVariantStatus.UNAVAILABLE

        logger.info(f"Availability checked for item {item.id}")
        return item, availability

    def get_distinct_field_values(self, model: type, field_name: str) -> list[str]:
        """
        Get distinct values for a field (for dropdown options)

        Args:
            model: SQLModel class (Item or ItemVariant)
            field_name: Name of the field

        Returns:
            Sorted list of distinct values
        """
        logger.debug(f"Fetching distinct {field_name} values from {model.__name__}")

        field_attr = getattr(model, field_name)
        stmt = select(field_attr).where(field_attr.is_not(None)).distinct()
        results = self.session.exec(stmt).all()

        # Filter out None and convert to strings
        filtered_results = [result for result in results if result is not None]

        logger.debug(f"Retrieved {len(filtered_results)} distinct {field_name} values")
        return sorted(filtered_results)
