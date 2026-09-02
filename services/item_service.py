from datetime import UTC, date, datetime
from uuid import UUID

from sqlmodel import Session, select

# --- Project Imports ---
from core.database import SessionDep
from core.exceptions import BadRequestException, ConflictException
from core.logger import logger
from core.query_gateway import QueryGateway
from models.item import Item, ItemCreate, ItemFilters, ItemUpdate
from models.item_variant import (
    ItemVariant,
    ItemVariantCreate,
    ItemVariantStatus,
    ItemVariantUpdate,
)
from services.helpers import ensure_utc, validate_time_period
from services.item_query_gateway import ItemQueryGateway
from services.item_variant_service import ItemVariantService


class ItemService:
    """Handles all business logic and database operations for Items"""

    def __init__(self, session: SessionDep):
        self.session: Session = session
        self.variant_service = ItemVariantService(session)
        self.query_gateway: QueryGateway[Item, ItemFilters] = ItemQueryGateway(session)

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
        if item.id is None:
            raise BadRequestException("Item creation did not produce an ID")

        # Create variants if provided
        if item_in.variants:
            for variant_in in item_in.variants:
                variant_create = ItemVariantCreate(
                    **variant_in.model_dump(), item_id=item.id
                )
                _ = self.variant_service.create(variant_create)

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

        if item.id is None:
            raise BadRequestException("Item must have an ID before it can be updated")

        update_data = item_in.model_dump(exclude={"variants"}, exclude_unset=True)

        variants_were_supplied = "variants" in item_in.model_fields_set
        if not update_data and not variants_were_supplied:
            logger.warning("No data provided for update")
            raise BadRequestException("No data provided for update")

        self._validate_title_uniqueness(item, update_data.get("title"))

        try:
            for field, value in update_data.items():
                setattr(item, field, value)

            if variants_were_supplied:
                self._sync_variants(item, item_in)
                item.updated_at = datetime.now(UTC)
                self.session.commit()
                self.session.refresh(item)
        except Exception:
            self.session.rollback()
            raise

        logger.info(f"Item updated successfully: {item.id}")
        return item

    def _validate_title_uniqueness(self, item: Item, title: str | None) -> None:
        """Raise if `title` is already used by a different item."""
        if not title or title == item.title:
            return

        stmt = select(Item.id).where(Item.title == title, Item.id != item.id)
        if self.session.exec(stmt).first():
            logger.warning(f"Title '{title}' already exists")
            raise ConflictException(f"Title '{title}' is already in use")

    def _sync_variants(self, item: Item, item_in: ItemUpdate) -> None:
        """Reconcile `item.variants` with the supplied variant list.

        Variants missing from `item_in.variants` are archived; archived
        variants matching a newly-supplied size/color are reused instead of
        creating a duplicate; the rest are created or updated as needed.
        """
        if item_in.variants is None:
            raise BadRequestException("variants must be a list when supplied")

        existing_variants_map = {v.id: v for v in item.variants}
        supplied_variant_ids = {
            variant_in.id
            for variant_in in item_in.variants
            if variant_in.id is not None
        }
        self._validate_supplied_variant_ids(
            item, existing_variants_map, supplied_variant_ids
        )

        # Archive removals before creating replacements
        removed_variant_ids = set(existing_variants_map) - supplied_variant_ids
        reusable_variants = self._archive_removed_variants(
            existing_variants_map, removed_variant_ids
        )

        for variant_in in item_in.variants:
            if variant_in.id is None:
                self._create_or_reuse_variant(item, variant_in, reusable_variants)
            else:
                _ = self.variant_service.update(
                    existing_variants_map[variant_in.id], variant_in, commit=False
                )

    def _validate_supplied_variant_ids(
        self,
        item: Item,
        existing_variants_map: dict[UUID | None, ItemVariant],
        supplied_variant_ids: set[UUID],
    ) -> None:
        for variant_id in supplied_variant_ids:
            if variant_id not in existing_variants_map:
                raise BadRequestException(
                    f"Variant {variant_id} does not belong to item {item.id}"
                )

    def _archive_removed_variants(
        self,
        existing_variants_map: dict[UUID | None, ItemVariant],
        removed_variant_ids: set[UUID | None],
    ) -> list[ItemVariant]:
        """Archive removed variants, returning them ordered for size/color reuse."""
        for variant_id in removed_variant_ids:
            logger.debug(f"Archiving variant {variant_id} (removed from item)")
            self.variant_service.delete(existing_variants_map[variant_id], commit=False)

        # Removed variants are candidates for reuse
        # by comparing them with the most recent ones.
        return sorted(
            (existing_variants_map[vid] for vid in removed_variant_ids),
            key=lambda v: ensure_utc(v.updated_at),
            reverse=True,
        )

    def _pop_reusable_variant(
        self,
        reusable_variants: list[ItemVariant],
        size: str | None,
        color: str | None,
    ) -> ItemVariant | None:
        size_key = self.variant_service.normalize_identity(size)
        color_key = self.variant_service.normalize_identity(color)
        for index, candidate in enumerate(reusable_variants):
            if candidate.size_key == size_key and candidate.color_key == color_key:
                return reusable_variants.pop(index)
        return None

    def _create_or_reuse_variant(
        self,
        item: Item,
        variant_in: ItemVariantUpdate,
        reusable_variants: list[ItemVariant],
    ) -> None:
        reused_variant = self._pop_reusable_variant(
            reusable_variants, variant_in.size, variant_in.color
        )
        if reused_variant is not None:
            logger.debug(
                f"Reusing archived variant {reused_variant.id} "
                + "for supplied variant with matching size/color"
            )
            _ = self.variant_service.update(
                reused_variant,
                variant_in.model_copy(update={"is_archived": False}),
                commit=False,
            )
            return

        variant_create = ItemVariantCreate(
            item_id=item.id,
            **variant_in.model_dump(exclude={"id"}, exclude_unset=True),
        )
        _ = self.variant_service.create(variant_create, commit=False)

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
        self,
        item: Item,
        start_time: date,
        end_time: date,
        exclude_order_id: int | None = None,
    ) -> tuple[Item, dict[UUID, int]]:
        """Check item variant availability for a time period.

        Returns (item, availability) where availability maps variant id to
        available_quantity, since that value isn't a persisted model field.
        """
        validate_time_period(start_time, end_time)

        logger.debug(
            f"Checking availability for item {item.id} from {start_time} to {end_time}"
        )

        # Update variant availability status
        availability: dict[UUID, int] = {}
        for variant in item.variants:
            if variant.id is None:
                continue
            is_available, available_quantity, reason = (
                self.variant_service.check_availability(
                    variant, start_time, end_time, exclude_order_id
                )
            )

            availability[variant.id] = available_quantity

            if not is_available:
                logger.debug(reason)
                if variant.status != ItemVariantStatus.CLEANING:
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
