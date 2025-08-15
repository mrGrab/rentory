import json
from uuid import UUID
from datetime import datetime, timezone, date
from fastapi import APIRouter, HTTPException, Depends, Query, status, Response
from fastapi.responses import JSONResponse
from sqlmodel import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from core.logger import logger
from core.dependency import (
    SessionDep,
    CurrentUser,
    get_current_user,
    get_current_superuser,
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


def _transform_to_public(item: Item) -> ItemPublic:
    order_ids = set()
    for variant in item.variants:
        for link in variant.order_links:
            order_ids.add(link.order_id)
    return ItemPublic.model_validate(item,
                                     update={"order_ids": list(order_ids)})


def _apply_filters(stmt, f: ItemFilters):
    """Apply all filters to the query statement."""

    if any([f.color, f.size, f.variant_status]):
        stmt = stmt.join(ItemVariant, Item.id == ItemVariant.item_id)

    # Item ID filter
    if f.id:
        if isinstance(f.id, list):
            stmt = stmt.where(Item.id.in_(f.id))
        else:
            stmt = stmt.where(Item.id.contains(f.id))
    # Item by name
    if f.title:
        stmt = stmt.where(Item.title.ilike(f"%{f.title}%"))
    if f.q:
        stmt = stmt.where(Item.title.ilike(f"%{f.q}%"))

    # Filter by category
    if f.category:
        stmt = stmt.where(Item.category == f.category)

    # Status filter
    if f.status:
        stmt = stmt.where(Item.status == f.status.value)

    # Tag filter
    if f.tag:
        stmt = stmt.where(Item.tags.contains(f.tag))

    # Color filter
    if f.color:
        stmt = stmt.where(ItemVariant.color == f.color)

    # Size filter
    if f.size:
        stmt = stmt.where(ItemVariant.size == f.size)

    # Variant filter
    if f.variant_status:
        stmt = stmt.where(ItemVariant.status == f.variant_status)

    return stmt.distinct()


def create_filters_endpoint(path: str, model: object, field: str):

    @router.get(path,
                response_model=list[str],
                summary=f"List items {field}",
                description=f"Retrieve a distinct list of item {field}.",
                dependencies=[Depends(get_current_user)])
    def endpoint(session: SessionDep):
        try:
            obj_field = getattr(model, field)
            stmt = select(obj_field).where(obj_field.is_not(None)).distinct()
            results = session.exec(stmt).all()
            return JSONResponse(results)
        except Exception as e:
            logger.error(f"Error fetching item {field}: {e}")
            raise HTTPException(status_code=500,
                                detail=f"Failed to fetch item {field}")


# Dynamic endpoints for dropdown filters
create_filters_endpoint("/categories", Item, "category")
create_filters_endpoint("/statuses", Item, "status")
create_filters_endpoint("/sizes", ItemVariant, "size")
create_filters_endpoint("/colors", ItemVariant, "color")
create_filters_endpoint("/variant_statuses", ItemVariant, "status")


@router.get("",
            summary="List items",
            description="Retrieve a paginated list of available items.",
            dependencies=[Depends(get_current_user)])
async def read_items(response: Response,
                     session: SessionDep,
                     filter_: str = Query("{}", alias="filter"),
                     range_: str = Query("[0, 500]", alias="range"),
                     sort: str = Query('["id","DESC"]', alias="sort")):
    try:
        # Parse inputs
        sort_field, sort_order = json.loads(sort)
        offset, limit = calculate_pagination(json.loads(range_))
        filter_dict = json.loads(filter_)
        filters = ItemFilters(**filter_dict)

        stmt = select(Item).options(
            selectinload(Item.variants).selectinload(ItemVariant.order_links))

        # Apply filters
        stmt = _apply_filters(stmt, filters)

        # Apply sorting
        stmt = apply_sorting(stmt, Item, sort_field, sort_order)

        # Total count
        total = get_total_count(session, stmt)

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)
        items = session.exec(stmt).all()

        # Build response models
        result = [_transform_to_public(item) for item in items]

        set_pagination_headers(response, offset, len(result), total)
        logger.info(f"Fetched {len(result)} items out of {total} total")
        return result

    except Exception as e:
        logger.error(f"Error fetching items: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve items")


@router.post("",
             response_model=ItemPublic,
             summary="Create a new item",
             description="Adds a new item to the catalog.",
             dependencies=[Depends(get_current_user)])
def create_item(session: SessionDep, item_in: ItemCreate):
    logger.debug(f"Creating new item with title='{item_in.title}'")
    now = datetime.now(timezone.utc)

    try:
        variants = []
        for variant_in in item_in.variants:
            prices = [
                ItemPrice(**price.model_dump()) for price in variant_in.prices
            ]
            variant = ItemVariant(**variant_in.model_dump(exclude={"prices"}),
                                  prices=prices)
            variants.append(variant)

        # Create the main Item
        item = Item(**item_in.model_dump(exclude={"variants"}),
                    created_at=now,
                    updated_at=now,
                    variants=variants)

        session.add(item)
        session.commit()
        session.refresh(item)

        logger.info(f"Item created successfully: {item.id}")
        return _transform_to_public(item)

    except IntegrityError as ie:
        session.rollback()
        if "unique constraint" in str(ie).lower():
            logger.warning(f"An item '{item_in.title}' already exists.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An item with title '{item_in.title}' already exists.")
    except Exception as e:
        session.rollback()
        logger.exception(f"Unexpected error while creating item: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create item")


@router.get("/availability/{id}",
            response_model=ItemPublic,
            summary="Get item by ID with variants availability",
            description="Fetch a single item and check availability.",
            dependencies=[Depends(get_current_user)])
def check_item_availability(session: SessionDep,
                            id: UUID,
                            start_time: date | None = None,
                            end_time: date | None = None):
    logger.debug(f"Fetching and check item with ID: {id}")

    stmt = select(Item).where(Item.id == id)
    item = session.exec(stmt).first()
    if not item:
        logger.warning(f"Item not found: {id}")
        raise HTTPException(status_code=404, detail="Item not found")

    if start_time and end_time:
        variant_ids = [v.id for v in item.variants]

        stmt = select(OrderItemLink.item_variant_id).join(Order)
        stmt = stmt.where(OrderItemLink.item_variant_id.in_(variant_ids))
        stmt = stmt.where(Order.start_time <= end_time, Order.end_time
                          >= start_time)
        result = session.exec(stmt.distinct()).all()

        for variant in item.variants:
            if variant.service_end_time and variant.service_end_time > start_time:
                variant.status = ItemVariantStatus.UNAVAILABLE
            elif variant.id in result:
                variant.status = ItemVariantStatus.UNAVAILABLE

    logger.info(f"Item retrieved: {item.id} - {item.title}")
    return _transform_to_public(item)


@router.get("/{id}",
            response_model=ItemPublic,
            summary="Get item by ID",
            description="Fetch a single item by its unique ID.",
            dependencies=[Depends(get_current_user)])
def read_item(session: SessionDep, id: UUID) -> ItemPublic:
    logger.debug(f"Fetching item with ID: {id}")

    stmt = select(Item).where(Item.id == id)

    item = session.exec(stmt).first()
    if not item:
        logger.warning(f"Item not found: {id}")
        raise HTTPException(status_code=404, detail="Item not found")

    logger.info(f"Item retrieved: {item.id} - {item.title}")
    return _transform_to_public(item)


@router.put("/{id}",
            response_model=ItemPublic,
            summary="Update item by ID",
            description="Update an existing item's details by its unique ID.",
            dependencies=[Depends(get_current_superuser)])
def update_item(session: SessionDep, id: UUID, item_in: ItemUpdate):
    logger.info(f"Updating item ID {id}")

    stmt = (select(Item).options(
        selectinload(Item.variants).selectinload(
            ItemVariant.prices)).where(Item.id == id))
    item = session.exec(stmt).one_or_none()
    if not item:
        logger.warning(f"Item with ID {id} not found")
        raise HTTPException(status_code=404, detail="Item not found")

    try:
        update_data = item_in.model_dump(exclude={"variants"},
                                         exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        # Handle variants if provided
        if hasattr(item_in, 'variants') and item_in.variants:
            existing_variants = {v.id: v for v in item.variants}
            updated_variants = []
            for variant_in in item_in.variants:
                if variant_in.id and variant_in.id in existing_variants:
                    # Update existing variant
                    variant_data = variant_in.model_dump(exclude={"prices"},
                                                         exclude_unset=True)
                    variant = existing_variants[variant_in.id]
                    for field, value in variant_data.items():
                        setattr(variant, field, value)
                else:
                    # Add new variant
                    variant_data = variant_in.model_dump(exclude={"prices"})
                    variant = ItemVariant(**variant_data)

                # Update prices
                variant.prices = [
                    ItemPrice(**price.model_dump())
                    for price in variant_in.prices
                ]
                updated_variants.append(variant)
            item.variants = updated_variants

        item.updated_at = datetime.now(timezone.utc)
        session.commit()

        logger.info(f"Item updated successfully: {item.id}")
        return _transform_to_public(item)

    except Exception as e:
        logger.exception(f"Failed to update item ID {id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update item")


@router.delete("/{id}",
               status_code=status.HTTP_200_OK,
               summary="Delete an item",
               description="Deletes an item by ID")
def delete_item(session: SessionDep, current_user: CurrentUser, id: UUID):
    logger.debug(
        f"Attempting to delete item '{id}' by '{current_user.username}'")

    item = session.get(Item, id)
    if not item:
        logger.warning(f"Item not found: ID='{id}'")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Item not found")
    if not current_user.is_superuser:
        logger.warning(
            f"Permission denied for '{current_user.username}' on item '{id}'")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not enough permissions")
    # Check if item is linked to any orders
    if item.order_links:
        logger.warning(f"Item '{id}' is linked to orders and cannot be deleted")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete item: it is linked to one or more orders")
    try:
        session.delete(item)
        session.commit()
        logger.info(f"Item deleted successfully: ID='{id}'")
        return JSONResponse(content={"message": "Item deleted successfully"},
                            status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.exception(f"Failed to delete item ID='{id}': {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to delete item")
