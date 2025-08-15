from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import select
import json
from core.logger import logger
from core.dependency import (
    SessionDep,
    CurrentUser,
    get_current_user,
    calculate_pagination,
    apply_sorting,
    get_total_count,
    set_pagination_headers,
)
from core.models import (
    Order,
    Client,
    OrderPublic,
    OrderCreate,
    OrderFilters,
    ItemVariant,
    OrderItemLink,
    OrderItemPublicInfo,
    PaymentDetails,
    DeliveryInfo,
    OrderUpdate,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


def _transform_to_public(order: Order) -> OrderPublic:
    """Convert DB Order to public schema."""
    order_data = order.model_dump(
        exclude={"item_links", "payment_details", "delivery_info"})
    payment_details = PaymentDetails(
        **order.payment_details) if order.payment_details else None
    delivery_info = DeliveryInfo(
        **order.delivery_info) if order.delivery_info else None
    return OrderPublic(**order_data,
                       payment_details=payment_details,
                       delivery_info=delivery_info,
                       items=[
                           OrderItemPublicInfo(
                               item_id=link.item_variant.item_id,
                               item_variant_id=link.item_variant_id,
                               size=link.item_variant.size,
                               color=link.item_variant.color,
                               status=link.item_variant.status,
                               quantity=link.quantity,
                               price=link.price) for link in order.item_links
                       ])


def _apply_filters(stmt, f: OrderFilters):
    """Apply all filters to the query statement."""

    # Phone filter
    if f.phone:
        stmt = stmt.join(Client).where(Client.phone.ilike(f"%{f.phone}%"))

    # Order ID filter
    if f.id:
        if isinstance(f.id, list):
            stmt = stmt.where(Order.id.in_(f.id))
        else:
            stmt = stmt.where(Order.id == f.id)

    # Client ID filter
    if f.client_id:
        stmt = stmt.where(Order.client_id == f.client_id)

    # Time range filters
    if f.start_time and f.end_time:
        # Orders that end after the filter start time
        stmt = stmt.where(Order.end_time >= f.start_time)
        # Orders that start before the filter end time
        stmt = stmt.where(Order.start_time <= f.end_time)
    if f.end_time and not f.start_time:
        stmt = stmt.where(Order.end_time == f.end_time)
    if f.start_time and not f.end_time:
        stmt = stmt.where(Order.start_time == f.start_time)

    # Tag filter
    if f.tag:
        stmt = stmt.where(Order.tags.contains(f.tag))

    # Status filter
    if f.status:
        stmt = stmt.where(Order.status == f.status)

    # Item IDs filter
    if f.item_ids:
        stmt = stmt.join(Order.item_links).join(OrderItemLink.item_variant)
        stmt = stmt.where(ItemVariant.item_id.in_(f.item_ids))

    # Pickup type filter
    if f.pickup_type:
        stmt = stmt.where(Order.delivery_info.pickup_type == f.pickup_type)

    return stmt.distinct()


def _get_and_validate_variants(session: SessionDep, variant_ids: list[str],
                               start_time: datetime, end_time: datetime):
    """Fetch variants and check validate availability."""
    # Get all variants
    stmt = select(ItemVariant).where(ItemVariant.id.in_(variant_ids))
    variants = session.exec(stmt).all()

    # Check if all variants exist
    if len(variants) != len(variant_ids):
        found_ids = {v.id for v in variants}
        missing_ids = set(variant_ids) - found_ids
        raise HTTPException(
            status_code=404,
            detail=f"Variants not found: {', '.join(map(str, missing_ids))}")

    # Check service availability
    for variant in variants:
        if variant.service_end_time and variant.service_end_time > start_time:
            raise HTTPException(
                status_code=400,
                detail=f"Variant {variant.id} is under maintenance")

    # Check all booking conflicts
    stmt = select(OrderItemLink.item_variant_id).join(Order)
    stmt = stmt.where(OrderItemLink.item_variant_id.in_(variant_ids))
    stmt = stmt.where(Order.status.not_in(["cancelled", "done"]))
    stmt = stmt.where(Order.start_time <= end_time, Order.end_time
                      >= start_time)
    conflicted_ids = {id for (id,) in session.exec(stmt).all()}

    if conflicted_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Variants already booked: {list(conflicted_ids)}")

    return variants


@router.get("",
            summary="List orders with pagination",
            description="Retrieve a paginated list of orders.",
            dependencies=[Depends(get_current_user)])
async def read_orders(response: Response,
                      session: SessionDep,
                      filter_: str = Query("{}", alias="filter"),
                      range_: str = Query("[0, 500]", alias="range"),
                      sort: str = Query('["created_at", "DESC"]',
                                        alias="sort")):
    try:
        # Parse query params
        sort_field, sort_order = json.loads(sort)
        offset, limit = calculate_pagination(json.loads(range_))
        filter_dict = json.loads(filter_)
        filters = OrderFilters(**filter_dict)

        stmt = select(Order)

        # Apply filters
        stmt = _apply_filters(stmt, filters)

        # Apply sorting
        stmt = apply_sorting(stmt, Order, sort_field, sort_order)

        # Total count
        total = get_total_count(session, stmt)

        # Fetch paginated orders
        paginated_stmt = stmt.offset(offset).limit(limit)
        orders = session.exec(paginated_stmt).all()

        # Transform to public schema
        result = [_transform_to_public(order) for order in orders]

        set_pagination_headers(response, offset, len(result), total)
        logger.info(f"Retrieved {len(result)} of {total} orders")
        return result

    except (ValueError, KeyError) as e:
        logger.error(f"Invalid query parameters: {e}")
        raise HTTPException(status_code=400, detail="Invalid query parameters")
    except Exception as e:
        logger.exception(f"Failed to retrieve orders: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve orders")


@router.get("/{id}",
            response_model=OrderPublic,
            summary="Get a specific order by ID",
            description="Retrieve details of a single order by its ID.",
            dependencies=[Depends(get_current_user)])
async def read_order(session: SessionDep, id: int) -> OrderPublic:
    logger.debug(f"Fetching order with ID: {id}")

    try:
        order = session.get(Order, id)
        if not order:
            logger.warning(f"Order not found: {id}")
            raise HTTPException(status_code=404,
                                detail=f"Order with ID {id} not found")
        logger.info(f"Order retrieved successfully: {order.id}")
        return _transform_to_public(order)

    except Exception as e:
        logger.exception(f"Failed to retrieve order with ID {id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve order")


@router.post("",
             summary="Create a new order",
             description="Create an order and link it to existing items.")
async def create_order(session: SessionDep,
                       order_in: OrderCreate,
                       current_user=Depends(get_current_user)):
    logger.debug(f"User {current_user.username} is creating a new order")
    now = datetime.now(timezone.utc)

    variant_ids = [item.item_variant_id for item in order_in.items]
    if not variant_ids:
        raise HTTPException(status_code=400,
                            detail="No item variants specified")

    try:
        # Validate item variants
        _get_and_validate_variants(session=session,
                                   variant_ids=variant_ids,
                                   start_time=order_in.start_time,
                                   end_time=order_in.end_time)

        order = Order(**order_in.model_dump(exclude={"items"},
                                            exclude_unset=True),
                      created_by_user_id=current_user.id,
                      created_at=now,
                      updated_at=now)
        session.add(order)
        session.flush()

        order_links = [
            OrderItemLink(
                order_id=order.id,
                item_variant_id=item.item_variant_id,
                quantity=item.quantity,
                price=item.price,
            ) for item in order_in.items
        ]
        session.add_all(order_links)
        session.commit()

        logger.info(f"Order {order.id} created successfully")
        return _transform_to_public(order)

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail="Failed to create order")


@router.put("/{id}",
            response_model=OrderPublic,
            summary="Update order by ID",
            description="Update an existing order's details by its unique ID.",
            dependencies=[Depends(get_current_user)])
def update_order(session: SessionDep, id: int, order_in: OrderUpdate):
    logger.info(f"Updating order ID: {id}")

    order = session.get(Order, id)
    if not order:
        logger.warning(f"Order not found: {id}")
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        # Update fields
        data = order_in.model_dump(exclude={"items"}, exclude_unset=True)
        for field, value in data.items():
            setattr(order, field, value)

        # Update item variants if provided
        if order_in.items:
            existing_links = {i.item_variant_id: i for i in order.item_links}
            updated_ids = set()

            for item in order_in.items:
                variant_id = item.item_variant_id
                updated_ids.add(variant_id)

                # Update existing variant
                if variant_id in existing_links:
                    link = existing_links[variant_id]
                    item_data = item.model_dump(exclude={"item_id"},
                                                exclude_unset=True)
                    for field, value in item_data.items():
                        setattr(link, field, value)
                # Add new variant
                else:
                    session.add(
                        OrderItemLink(**item.model_dump(), order_id=order.id))

            # Delete variants not in the update payload
            for old_id in existing_links.keys() - updated_ids:
                session.delete(existing_links[old_id])

        order.updated_at = datetime.now(timezone.utc)
        session.commit()

        logger.info(f"Order updated successfully: {order.id}")
        return _transform_to_public(order)

    except Exception as e:
        logger.exception(f"Failed to update order ID {id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update order")


@router.delete("/{id}",
               status_code=status.HTTP_200_OK,
               summary="Delete an order",
               description="Deletes an order by ID")
def delete_order(session: SessionDep, id: int, current_user: CurrentUser):
    logger.debug(
        f"Attempting to delete Order '{id}' by '{current_user.username}'")

    order = session.get(Order, id)
    if order is None:
        logger.warning(f"Order not found: ID='{id}'")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Order not found")

    if not current_user.is_superuser:
        logger.warning(
            f"Permission denied for '{current_user.username}' on order '{id}'")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not enough permissions")

    try:
        session.delete(order)
        session.commit()
        logger.info(f"Order deleted successfully: ID='{id}'")
        return JSONResponse(content={"message": "Order deleted successfully"},
                            status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.exception(f"Failed to delete order ID='{id}': {e}")
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to delete order")
