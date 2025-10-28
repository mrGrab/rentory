from uuid import UUID
from datetime import datetime, timezone, date
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status, Response, Depends
from sqlmodel import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy import text

# --- Project Imports ---
import core.query_utils as qp
from core.logger import logger
from core.dependencies import CurrentUser, CurrentSuperuser
from core.database import SessionDep
from core.exceptions import (
    InternalErrorException,
    ConflictException,
    NotFoundException,
    BadRequestException,
)
from core.models import (
    Item,
    ItemFilters,
    ItemPublic,
    ItemCreate,
    ItemUpdate,
    ItemVariant,
    ItemPrice,
    Order,
    OrderItemLink,
    ItemVariantStatus,
)


class ItemService:
    """Handles all business logic and database operations for Items."""

    def __init__(self, session: SessionDep):
        self.session = session

    def get_item_by_id(self, item_id: UUID) -> Item:
        """Retrieves an item by its ID with all relationships eagerly loaded."""
        stmt = select(Item).where(Item.id == item_id).options(
            selectinload(Item.variants).selectinload(ItemVariant.prices),
            selectinload(Item.variants).selectinload(ItemVariant.order_links))
        item = self.session.exec(stmt).first()
        if not item:
            raise NotFoundException("Item not found")
        return item

    def get_all_items(self, filters: ItemFilters, offset: int, limit: int,
                      sort_field: str,
                      sort_order: str) -> tuple[List[Item], int]:
        """Retrieves a paginated list of items based on filters."""
        stmt = select(Item).options(
            selectinload(Item.variants).selectinload(ItemVariant.order_links))
        stmt = self._apply_filters(stmt, filters)
        total = qp.get_total_count(self.session, stmt)
        stmt = qp.apply_sorting(stmt, Item, sort_field, sort_order)
        stmt = stmt.offset(offset).limit(limit)
        items = self.session.exec(stmt).all()
        return items, total

    def create_item(self, item_in: ItemCreate) -> Item:
        """Creates a new item, its variants, and their prices."""
        # Check for duplicate title
        stmt = select(Item.id).where(Item.title == item_in.title)
        existing_item = self.session.exec(stmt).first()
        if existing_item:
            raise ConflictException(
                f"Item with title '{item_in.title}' already exists")

        item = Item(**item_in.model_dump(exclude={"variants"}))

        # Create variants with their prices
        for variant_in in item_in.variants:
            variant_data = variant_in.model_dump(exclude={"prices"})
            prices = [ItemPrice(**p.model_dump()) for p in variant_in.prices]
            item.variants.append(ItemVariant(**variant_data, prices=prices))

        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def update_item(self, item: Item, item_in: ItemUpdate) -> Item:
        """Updates an item, including its nested variants and prices."""

        # Update basic properties of the Item
        item_data = item_in.model_dump(exclude={"variants"}, exclude_unset=True)
        for field, value in item_data.items():
            setattr(item, field, value)

        existing_variants_map = {v.id: v for v in item.variants if v.is_active}
        incoming_variant_ids = {v.id for v in item_in.variants if v.id}

        print(existing_variants_map.keys())
        print(incoming_variant_ids)

        # Process incoming variants
        for variant_in in item_in.variants:
            if not variant_in.id:
                # Create brand new variants
                logger.info("Adding new variant")
                item.variants.append(self.create_variant_from_input(variant_in))
                continue

            existing_variant = existing_variants_map.get(variant_in.id)
            if not existing_variant:
                continue

            if self.variant_has_changes(existing_variant, variant_in):
                # Update existing variant
                self.update_or_archive_variant(existing_variant, variant_in,
                                               item)

        # Handle removed variants
        ids_to_remove = set(existing_variants_map.keys()) - incoming_variant_ids
        for variant_id in ids_to_remove:
            variant_to_remove = existing_variants_map.get(variant_id)
            if variant_to_remove.order_links:
                logger.info(f"Archiving removed variant {variant_to_remove.id}")
                variant_to_remove.is_active = False
            else:
                logger.info(f"Deleting removed variant {variant_to_remove.id}")
                self.session.delete(variant_to_remove)

        item.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(item)
        return item

    def price_has_changes(self, existing_prices, incoming_prices) -> bool:
        """Compare existing prices with incoming data to detect changes."""

        if len(existing_prices) != len(incoming_prices):
            return True

        sorted_incoming = sorted(incoming_prices,
                                 key=lambda field: field.price_type)
        sorted_existing = sorted(existing_prices,
                                 key=lambda field: field.price_type)

        print(sorted_incoming)
        print(sorted_existing)
        for index, variant in enumerate(sorted_incoming):
            for field, new_value in variant.model_dump().items():
                if getattr(sorted_existing[index], field, None) != new_value:
                    return True
        logger.debug("No changes in prices")
        return False

    def variant_has_changes(self, existing: ItemVariant, incoming) -> bool:
        """Compare existing variant with incoming data to detect changes."""

        # Compare variant fields
        incoming_data = incoming.model_dump(exclude={"id", "prices"})
        for field, new_value in incoming_data.items():
            if getattr(existing, field, None) != new_value:
                logger.debug(f"Field {field} has changed")
                return True

        # Compare prices
        if self.price_has_changes(existing.prices, incoming.prices):
            logger.debug("Prices has been changed")
            return True
        logger.debug("No changes in variant")
        return False

    def _apply_filters(self, stmt, filters: ItemFilters):
        """Applies all filters to the item query statement."""

        # Join ItemVariant if any variant-specific filters are present
        if any([filters.color, filters.size, filters.variant_status]):
            stmt = stmt.join(ItemVariant, Item.id == ItemVariant.item_id)

        if filters.id:
            if isinstance(filters.id, list):
                stmt = stmt.where(Item.id.in_(filters.id))
            else:
                stmt = stmt.where(Item.id.contains(filters.id))
        if filters.title:
            stmt = stmt.where(text("title REGEXP :pattern")).params(
                pattern=f"^{filters.title}")
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

    def create_variant_from_input(self, variant_in) -> ItemVariant:
        """Create a new ItemVariant from input data."""
        variant_data = variant_in.model_dump(exclude={"prices", "id"})
        prices = [ItemPrice(**p.model_dump()) for p in variant_in.prices]
        return ItemVariant(**variant_data, prices=prices)

    def update_or_archive_variant(self, existing_variant: ItemVariant,
                                  variant_in, item: Item) -> None:
        """Update variant in-place or archive and create new one."""
        if existing_variant.order_links:
            # Archive existing and create new
            logger.info(
                f"Archiving variant {existing_variant.id} due to update")
            existing_variant.is_active = False

            logger.info(
                f"Creating new variant instead of {existing_variant.id}")
            new_variant = self.create_variant_from_input(variant_in)
            item.variants.append(new_variant)
        else:
            # Update in-place (no orders)
            logger.info(f"Updating variant {existing_variant.id} in-place")
            update_data = variant_in.model_dump(exclude={"prices", "id"})
            for field, value in update_data.items():
                setattr(existing_variant, field, value)
            existing_variant.prices = [
                ItemPrice(**p.model_dump()) for p in variant_in.prices
            ]


def get_item_or_404(item_id: UUID, session: SessionDep) -> Item:
    """Dependency to retrieve an item by ID or raise a NotFoundException."""
    service = ItemService(session)
    return service.get_item_by_id(item_id)


def transform_item_to_public(item: Item) -> ItemPublic:
    """Transform database Item to public schema with order IDs"""
    order_ids = set()
    for variant in item.variants:
        for link in variant.order_links:
            order_ids.add(link.order_id)

    return ItemPublic.model_validate(item,
                                     update={"order_ids": list(order_ids)})


router = APIRouter(prefix="/items", tags=["Items"])


def create_dropdown_endpoint(path: str, model: type, field_name: str):
    """Create a dropdown endpoint for distinct field values"""

    @router.get(path,
                response_model=List[str],
                summary=f"Get {field_name} options")
    def get_field_options(session: SessionDep,
                          current_user: CurrentUser) -> List[str]:
        """Get distinct field values for dropdown"""
        try:
            field_attr = getattr(model, field_name)
            stmt = select(field_attr).where(field_attr.is_not(None)).distinct()
            results = session.exec(stmt).all()

            # Filter out None values and convert to strings
            filtered_results = [
                str(result) for result in results if result is not None
            ]

            logger.debug(
                f"Retrieved {len(filtered_results)} {field_name} options")
            return sorted(filtered_results)

        except Exception as e:
            logger.error(f"Error fetching {field_name} options: {e}")
            raise InternalErrorException(
                f"Failed to fetch {field_name} options")

    return get_field_options


# Create dropdown endpoints
create_dropdown_endpoint("/categories", Item, "category")
create_dropdown_endpoint("/statuses", Item, "status")
create_dropdown_endpoint("/sizes", ItemVariant, "size")
create_dropdown_endpoint("/colors", ItemVariant, "color")
create_dropdown_endpoint("/variant-statuses", ItemVariant, "status")


@router.get("",
            response_model=List[ItemPublic],
            summary="List items with pagination",
            description="Retrieve a paginated list of items")
def read_items(response: Response,
               session: SessionDep,
               current_user: CurrentUser,
               filter_: str = Query("{}", alias="filter"),
               range_: str = Query("[0, 500]", alias="range"),
               sort: str = Query('["id","DESC"]', alias="sort")):
    """List items with filtering, sorting, and pagination"""

    try:
        service = ItemService(session)
        filter_dict, range_list, sort_field, sort_order = qp.parse_params(
            filter_, range_, sort)
        filters = ItemFilters(**filter_dict)
        offset, limit = qp.calculate_pagination(range_list)

        items, total = service.get_all_items(filters, offset, limit, sort_field,
                                             sort_order)

        result = [transform_item_to_public(item) for item in items]
        qp.set_pagination_headers(response, offset, len(result), total)

        logger.info(
            f"Retrieved {len(result)} of {total} items for user {current_user.username}"
        )
        return result
    except HTTPException:
        raise  # Re-raise HTTP exceptions from parse_query_params
    except Exception as e:
        logger.error(f"Failed to retrieve items: {e}")
        raise InternalErrorException("Failed to retrieve items")


@router.get("/{item_id}",
            response_model=ItemPublic,
            summary="Get item by ID",
            description="Retrieve a specific item by its ID")
def read_item(current_user: CurrentUser, item: Item = Depends(get_item_or_404)):
    """Get a specific item by ID"""
    logger.debug(f"User {current_user.username} fetching item {item.id}")
    return transform_item_to_public(item)


@router.get("/{item_id}/availability",
            response_model=ItemPublic,
            summary="Check item availability",
            description="Get item with availability status")
def check_item_availability(session: SessionDep,
                            current_user: CurrentUser,
                            item_id: UUID,
                            start_time: Optional[date] = None,
                            end_time: Optional[date] = None):
    """Check item availability for a specific time period"""
    logger.debug(
        f"User {current_user.username} checking availability for item {item_id} from {start_time} to {end_time}"
    )

    item = session.get(Item, item_id)
    if not item:
        raise NotFoundException

    # Check availability if time range is provided
    if start_time and end_time:
        if start_time > end_time:
            raise BadRequestException("Start time must be before end time")

        variant_ids = [v.id for v in item.variants]

        # Find variants that are booked during the requested period
        stmt = select(OrderItemLink.item_variant_id).join(Order)
        stmt = stmt.where(OrderItemLink.item_variant_id.in_(variant_ids))
        stmt = stmt.where(Order.status.not_in(["cancelled", "done"]))
        stmt = stmt.where(Order.start_time <= end_time)
        stmt = stmt.where(Order.end_time >= start_time)
        booked_variant_ids = session.exec(stmt.distinct()).all()

        # Update variant availability status
        for variant in item.variants:
            # Check if variant is booked
            if variant.id in booked_variant_ids:
                variant.status = ItemVariantStatus.UNAVAILABLE
                continue
            # Check if variant is under maintenance
            if variant.service_end_time and variant.service_end_time > start_time:
                variant.status = ItemVariantStatus.UNAVAILABLE

    logger.info(f"Availability checked for item: {item.id} - {item.title}")
    return transform_item_to_public(item)


@router.post("",
             response_model=ItemPublic,
             status_code=status.HTTP_201_CREATED,
             summary="Create new item",
             description="Create a new item with variants and prices")
def create_item(session: SessionDep, current_user: CurrentUser,
                item_in: ItemCreate):
    """Create a new item"""
    logger.info(f"Creating new item: {item_in.title}")

    try:
        service = ItemService(session)
        item = service.create_item(item_in)
        logger.info(f"Item created successfully: {item.id}")
        return transform_item_to_public(item)
    except HTTPException as error:
        logger.error(error.detail)
        raise error
    except Exception as error:
        session.rollback()
        logger.error(error)
        raise InternalErrorException("Failed to create item")


@router.put("/{item_id}",
            response_model=ItemPublic,
            summary="Update item",
            description="Update an existing item (superuser only)")
def update_item(session: SessionDep,
                current_user: CurrentSuperuser,
                item_in: ItemUpdate,
                item: Item = Depends(get_item_or_404)):
    """Update an existing item"""
    logger.info(f"User {current_user.username} updating item {item.id}")

    try:
        service = ItemService(session)
        item = service.update_item(item, item_in)
        logger.info(f"Item updated successfully: {item.id}")
        return transform_item_to_public(item)
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update item {item.id}: {e}")
        raise InternalErrorException("Failed to update item")


@router.delete("/{item_id}",
               status_code=status.HTTP_200_OK,
               summary="Delete item",
               description="Delete an item by ID")
def delete_item(session: SessionDep, current_user: CurrentUser, item_id: UUID):
    """Delete an item"""
    logger.debug(
        f"User {current_user.username} attempting to delete item {item_id}")

    # Get the item
    item = session.get(Item, item_id)
    if not item:
        raise NotFoundException

    # Check if item has any active orders
    stmt = select(func.count(OrderItemLink.order_id))
    stmt = stmt.join(Order, OrderItemLink.order_id == Order.id)
    stmt = stmt.join(ItemVariant,
                     OrderItemLink.item_variant_id == ItemVariant.id)
    stmt = stmt.where(ItemVariant.item_id == item_id,
                      Order.status.not_in(["cancelled", "done"]))
    active_orders_count = session.exec(stmt).one()
    if active_orders_count > 0:
        logger.warning(
            f"Item {item_id} has active orders and cannot be deleted")
        raise BadRequestException("Cannot delete item: it has active orders")

    try:
        session.delete(item)
        session.commit()

        logger.info(
            f"Item {item_id} deleted successfully by {current_user.username}")
        return {"message": f"Item {item_id} deleted successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete item {item_id}: {e}")
        raise InternalErrorException("Failed to delete item")
