from uuid import UUID
from datetime import datetime, timezone, date
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status, Response
from sqlmodel import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy import text

from core.logger import logger
from core.dependencies import SessionDep, CurrentUser
from core.database import (
    parse_query_params,
    calculate_pagination,
    apply_sorting,
    get_total_count,
    set_pagination_headers,
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

router = APIRouter(prefix="/items", tags=["Items"])


def transform_item_to_public(item: Item) -> ItemPublic:
    """Transform database Item to public schema with order IDs"""
    order_ids = set()
    for variant in item.variants:
        for link in variant.order_links:
            order_ids.add(link.order_id)

    return ItemPublic.model_validate(item,
                                     update={"order_ids": list(order_ids)})


def apply_item_filters(stmt, filters: ItemFilters):
    """Apply all filters to the item query statement"""

    # Join ItemVariant if any variant-specific filters are present
    if any([filters.color, filters.size, filters.variant_status]):
        stmt = stmt.join(ItemVariant, Item.id == ItemVariant.item_id)

    # Item ID filter
    if filters.id:
        if isinstance(filters.id, list):
            stmt = stmt.where(Item.id.in_(filters.id))
        else:
            stmt = stmt.where(Item.id.contains(filters.id))

    # Title filters (both title and q for search)
    if filters.title:
        stmt = stmt.where(
            text("title REGEXP :pattern")).params(pattern=f"^{filters.title}")

    if filters.q:
        stmt = stmt.where(Item.title.ilike(f"%{filters.q}%"))

    # Category filter
    if filters.category:
        stmt = stmt.where(Item.category == filters.category)

    # Status filter
    if filters.status:
        stmt = stmt.where(Item.status == filters.status.value)

    # Tag filter
    if filters.tag:
        stmt = stmt.where(Item.tags.contains(filters.tag))

    # Variant-specific filters
    if filters.color:
        stmt = stmt.where(ItemVariant.color == filters.color)

    if filters.size:
        stmt = stmt.where(ItemVariant.size == filters.size)

    if filters.variant_status:
        stmt = stmt.where(ItemVariant.status == filters.variant_status)

    return stmt.distinct()


def create_dropdown_endpoint(path: str, model: type, field_name: str):
    """Create a dropdown endpoint for distinct field values"""

    @router.get(
        path,
        response_model=List[str],
        summary=f"Get {field_name} options",
        description=
        f"Retrieve distinct list of {field_name} values for dropdown filters")
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch {field_name} options")

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
def read_items(
        response: Response,
        session: SessionDep,
        current_user: CurrentUser,
        filter_: str = Query("{}", alias="filter"),
        range_: str = Query("[0, 500]", alias="range"),
        sort: str = Query('["id","DESC"]', alias="sort"),
) -> List[ItemPublic]:
    """List items with filtering, sorting, and pagination"""

    try:
        # Parse query parameters
        filter_dict, range_list, sort_field, sort_order = parse_query_params(
            filter_, range_, sort)

        # Build filters and pagination
        filters = ItemFilters(**filter_dict)
        offset, limit = calculate_pagination(range_list)

        # Build query with eager loading for performance
        stmt = select(Item).options(
            selectinload(Item.variants).selectinload(ItemVariant.order_links))

        # Apply filters and sorting
        stmt = apply_item_filters(stmt, filters)
        stmt = apply_sorting(stmt, Item, sort_field, sort_order)

        # Get total count before pagination
        total = get_total_count(session, stmt)

        # Apply pagination and execute
        stmt = stmt.offset(offset).limit(limit)
        items = session.exec(stmt).all()

        # Transform to public schema
        result = [transform_item_to_public(item) for item in items]

        # Set pagination headers
        set_pagination_headers(response, offset, len(result), total)

        logger.info(
            f"Retrieved {len(result)} of {total} items for user {current_user.username}"
        )
        return result

    except HTTPException:
        raise  # Re-raise HTTP exceptions from parse_query_params
    except Exception as e:
        logger.error(f"Failed to retrieve items: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to retrieve items")


@router.post("",
             response_model=ItemPublic,
             status_code=status.HTTP_201_CREATED,
             summary="Create new item",
             description="Create a new item with variants and prices")
def create_item(session: SessionDep, current_user: CurrentUser,
                item_in: ItemCreate) -> ItemPublic:
    """Create a new item"""
    logger.debug(f"User {current_user.username} creating item: {item_in.title}")

    # Check for duplicate title
    stmt = select(Item.id).where(Item.title == item_in.title)
    existing_item = session.exec(stmt).one_or_none()
    if existing_item:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item with title '{item_in.title}' already exists")

    try:
        # Create variants with their prices
        variants = []
        for variant_in in item_in.variants:
            # Create prices for this variant
            prices = [ItemPrice(**p.model_dump()) for p in variant_in.prices]
            # Create variant with prices
            variant = ItemVariant(**variant_in.model_dump(exclude={"prices"}),
                                  prices=prices)
            variants.append(variant)

        # Create the main item
        item = Item(**item_in.model_dump(exclude={"variants"}),
                    variants=variants)

        session.add(item)
        session.commit()
        session.refresh(item)

        logger.info(
            f"Item created successfully: {item.id} by {current_user.username}")
        return transform_item_to_public(item)

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create item {item_in.title}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create item")


@router.get("/{item_id}/availability",
            response_model=ItemPublic,
            summary="Check item availability",
            description="Get item with availability status")
def check_item_availability(session: SessionDep,
                            current_user: CurrentUser,
                            item_id: UUID,
                            start_time: Optional[date] = None,
                            end_time: Optional[date] = None) -> ItemPublic:
    """Check item availability for a specific time period"""
    logger.debug(
        f"User {current_user.username} checking availability for item {item_id} from {start_time} to {end_time}"
    )

    item = session.get(Item, item_id)
    if not item:
        logger.warning(f"Item not found: {item_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Item not found")

    # Check availability if time range is provided
    if start_time and end_time:
        if start_time > end_time:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Start time must be before end time")

        variant_ids = [v.id for v in item.variants]

        # Find variants that are booked during the requested period
        booking_stmt = select(OrderItemLink.item_variant_id).join(Order)
        booking_stmt = booking_stmt.where(
            OrderItemLink.item_variant_id.in_(variant_ids),
            Order.status.not_in(["cancelled", "done"]), Order.start_time
            <= end_time, Order.end_time >= start_time)
        booked_variant_ids = session.exec(booking_stmt.distinct()).all()

        # Update variant availability status
        for variant in item.variants:
            # Check if variant is under maintenance
            if variant.service_end_time and variant.service_end_time > start_time:
                variant.status = ItemVariantStatus.UNAVAILABLE
            # Check if variant is booked
            elif variant.id in booked_variant_ids:
                variant.status = ItemVariantStatus.UNAVAILABLE

    logger.info(f"Availability checked for item: {item.id} - {item.title}")
    return transform_item_to_public(item)


@router.get("/{item_id}",
            response_model=ItemPublic,
            summary="Get item by ID",
            description="Retrieve a specific item by its ID")
def read_item(session: SessionDep, current_user: CurrentUser,
              item_id: UUID) -> ItemPublic:
    """Get a specific item by ID"""
    logger.debug(f"User {current_user.username} fetching item {item_id}")

    item = session.get(Item, item_id)
    if not item:
        logger.warning(f"Item not found: {item_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Item not found")

    logger.info(f"Item retrieved: {item.id} - {item.title}")
    return transform_item_to_public(item)


@router.put("/{item_id}",
            response_model=ItemPublic,
            summary="Update item",
            description="Update an existing item (superuser only)")
def update_item(session: SessionDep, current_user: CurrentUser, item_id: UUID,
                item_in: ItemUpdate) -> ItemPublic:
    """Update an existing item"""
    logger.info(f"User {current_user.username} updating item {item_id}")

    # Get item with all relationships loaded
    stmt = select(Item).options(
        selectinload(Item.variants).selectinload(
            ItemVariant.prices)).where(Item.id == item_id)
    item = session.exec(stmt).one_or_none()
    if not item:
        logger.warning(f"Item not found for update: {item_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Item not found")
    try:
        # Update basic item fields
        update_data = item_in.model_dump(exclude={"variants"},
                                         exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        # Update variants if provided
        if hasattr(item_in, 'variants') and item_in.variants:
            existing_variants = {v.id: v for v in item.variants}
            updated_variants = []

            for variant_in in item_in.variants:
                if variant_in.id and variant_in.id in existing_variants:
                    # Update existing variant
                    variant = existing_variants[variant_in.id]
                    variant_data = variant_in.model_dump(exclude={"prices"},
                                                         exclude_unset=True)
                    for field, value in variant_data.items():
                        if field != "id":  # Don't update the ID
                            setattr(variant, field, value)
                else:
                    # Create new variant
                    variant_data = variant_in.model_dump(exclude={"prices"})
                    variant = ItemVariant(**variant_data)

                # Update variant prices
                if variant_in.prices:
                    variant.prices = [
                        ItemPrice(**price.model_dump())
                        for price in variant_in.prices
                    ]

                updated_variants.append(variant)

            item.variants = updated_variants

        # Update timestamp
        item.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(item)

        logger.info(f"Item updated successfully: {item_id}")
        return transform_item_to_public(item)

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update item {item_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to update item")


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
        logger.warning(f"Item not found for deletion: {item_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Item not found")

    # Check if item has any active orders
    active_orders_stmt = select(func.count(OrderItemLink.order_id)).join(
        ItemVariant, OrderItemLink.item_variant_id == ItemVariant.id).join(
            Order, OrderItemLink.order_id == Order.id).where(
                ItemVariant.item_id == item_id,
                Order.status.not_in(["cancelled", "done"]))

    active_orders_count = session.exec(active_orders_stmt).one()
    if active_orders_count > 0:
        logger.warning(
            f"Item {item_id} has active orders and cannot be deleted")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot delete item: it has active orders")

    try:
        session.delete(item)
        session.commit()

        logger.info(
            f"Item {item_id} deleted successfully by {current_user.username}")
        return {"message": f"Item {item_id} deleted successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete item {item_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to delete item")
