from uuid import UUID
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlmodel import select

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


def transform_order_to_public(order: Order) -> OrderPublic:
    """Transform database Order to public schema"""
    # Extract base order data
    order_data = order.model_dump(
        exclude={"item_links", "payment_details", "delivery_info"})

    # Transform nested objects
    payment_details = None
    if order.payment_details:
        payment_details = PaymentDetails(**order.payment_details)

    delivery_info = None
    if order.delivery_info:
        delivery_info = DeliveryInfo(**order.delivery_info)

    # Transform order items
    items = []
    for link in order.item_links:
        item_info = OrderItemPublicInfo(item_id=link.item_variant.item_id,
                                        item_variant_id=link.item_variant_id,
                                        size=link.item_variant.size,
                                        color=link.item_variant.color,
                                        status=link.item_variant.status,
                                        quantity=link.quantity,
                                        price=link.price)
        items.append(item_info)

    return OrderPublic(**order_data,
                       payment_details=payment_details,
                       delivery_info=delivery_info,
                       items=items)


def apply_order_filters(stmt, filters: OrderFilters):
    """Apply all filters to the order query"""

    # Phone filter (requires join with Client)
    if filters.phone:
        stmt = stmt.join(Client).where(Client.phone.ilike(f"%{filters.phone}%"))

    # Order ID filter
    if filters.id:
        if isinstance(filters.id, list):
            stmt = stmt.where(Order.id.in_(filters.id))
        else:
            stmt = stmt.where(Order.id == filters.id)

    # Client ID filter
    if filters.client_id:
        stmt = stmt.where(Order.client_id == filters.client_id)

    # Time range filters (handle overlapping ranges)
    if filters.start_time and filters.end_time:
        # Find orders that overlap with the filter time range
        stmt = stmt.where(Order.end_time >= filters.start_time, Order.start_time
                          <= filters.end_time)
    elif filters.end_time:
        stmt = stmt.where(Order.end_time == filters.end_time)
    elif filters.start_time:
        stmt = stmt.where(Order.start_time == filters.start_time)

    # Tag filter
    if filters.tag:
        stmt = stmt.where(Order.tags.contains(filters.tag))

    # Status filter
    if filters.status:
        stmt = stmt.where(Order.status == filters.status)

    # Item IDs filter (requires joins)
    if filters.item_ids:
        stmt = stmt.join(Order.item_links).join(OrderItemLink.item_variant)
        stmt = stmt.where(ItemVariant.item_id.in_(filters.item_ids))

    # Pickup type filter (JSON field query)
    if filters.pickup_type:
        stmt = stmt.where(
            Order.delivery_info.pickup_type == filters.pickup_type)

    return stmt.distinct()


def validate_item_variants(session: SessionDep, variant_ids: List[UUID],
                           start_time: datetime,
                           end_time: datetime) -> List[ItemVariant]:
    """Validate item variants availability for the given time period"""

    # Fetch all requested variants
    stmt = select(ItemVariant).where(ItemVariant.id.in_(variant_ids))
    variants = session.exec(stmt).all()

    # Check if all variants exist
    if len(variants) != len(variant_ids):
        found_ids = {str(v.id) for v in variants}
        missing_ids = set(variant_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variants not found: {', '.join(missing_ids)}")

    # Check service availability (maintenance periods)
    for variant in variants:
        if variant.service_end_time and variant.service_end_time > start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=
                f"Variant {variant.id} is under maintenance until {variant.service_end_time}"
            )

    # Check for booking conflicts
    conflict_stmt = select(OrderItemLink.item_variant_id).join(Order)
    conflict_stmt = conflict_stmt.where(
        OrderItemLink.item_variant_id.in_(variant_ids),
        Order.status.not_in(["cancelled", "done"]), Order.start_time
        <= end_time, Order.end_time >= start_time)

    conflicted_ids = {str(id) for (id,) in session.exec(conflict_stmt).all()}
    if conflicted_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=
            f"Variants already booked during this time: {', '.join(conflicted_ids)}"
        )

    return variants


@router.get(
    "",
    response_model=List[OrderPublic],
    summary="List orders with pagination",
    description="Retrieve a paginated list of orders with filtering and sorting"
)
def read_orders(
    response: Response,
    session: SessionDep,
    current_user: CurrentUser,
    filter_: str = Query("{}", alias="filter"),
    range_: str = Query("[0, 500]", alias="range"),
    sort: str = Query('["created_at", "DESC"]', alias="sort")
) -> List[OrderPublic]:
    """List orders with filtering, sorting, and pagination"""

    try:
        # Parse query parameters using the utility function
        filter_dict, range_list, sort_field, sort_order = parse_query_params(
            filter_, range_, sort)

        # Build filters and pagination
        filters = OrderFilters(**filter_dict)
        offset, limit = calculate_pagination(range_list)

        # Build base query
        stmt = select(Order)
        stmt = apply_order_filters(stmt, filters)
        stmt = apply_sorting(stmt, Order, sort_field, sort_order)

        # Get total count before pagination
        total = get_total_count(session, stmt)

        # Apply pagination and execute
        stmt = stmt.offset(offset).limit(limit)
        orders = session.exec(stmt).all()

        # Transform to public schema
        result = [transform_order_to_public(order) for order in orders]

        # Set response headers
        set_pagination_headers(response, offset, len(result), total)

        logger.info(
            f"Retrieved {len(result)} of {total} orders for user {current_user.username}"
        )
        return result

    except HTTPException:
        raise  # Re-raise HTTP exceptions from parse_query_params
    except Exception as e:
        logger.error(f"Failed to retrieve orders: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to retrieve orders")


@router.get("/{order_id}",
            response_model=OrderPublic,
            summary="Get order by ID",
            description="Retrieve details of a specific order by its ID")
def read_order(session: SessionDep, current_user: CurrentUser,
               order_id: int) -> OrderPublic:
    """Get a specific order by ID"""
    logger.debug(f"User {current_user.username} fetching order {order_id}")

    order = session.get(Order, order_id)
    if not order:
        logger.warning(f"Order not found: {order_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Order with ID {order_id} not found")

    logger.info(f"Order {order_id} retrieved successfully")
    return transform_order_to_public(order)


@router.post("",
             response_model=OrderPublic,
             status_code=status.HTTP_201_CREATED,
             summary="Create a new order",
             description="Create a new order and link it to item variants")
def create_order(session: SessionDep, current_user: CurrentUser,
                 order_in: OrderCreate) -> OrderPublic:
    """Create a new order"""
    logger.debug(f"User {current_user.username} creating new order")

    # Validate input
    if not order_in.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Order must contain at least one item")

    try:
        # Validate item variants availability
        variant_ids = [item.item_variant_id for item in order_in.items]
        validate_item_variants(session=session,
                               variant_ids=variant_ids,
                               start_time=order_in.start_time,
                               end_time=order_in.end_time)

        # Create the order
        order_data = order_in.model_dump(exclude={"items"}, exclude_unset=True)
        order = Order(**order_data, created_by_user_id=current_user.id)
        session.add(order)
        session.flush()  # Get the order ID

        # Create order-item links
        order_links = []
        for item in order_in.items:
            link = OrderItemLink(order_id=order.id,
                                 item_variant_id=item.item_variant_id,
                                 quantity=item.quantity,
                                 price=item.price)
            order_links.append(link)

        session.add_all(order_links)
        session.commit()
        session.refresh(order)  # Load relationships

        logger.info(
            f"Order {order.id} created successfully by {current_user.username}")
        return transform_order_to_public(order)

    except HTTPException:
        session.rollback()
        raise  # Re-raise validation errors
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create order")


@router.put("/{order_id}",
            response_model=OrderPublic,
            summary="Update order",
            description="Update an existing order by its ID")
def update_order(session: SessionDep, current_user: CurrentUser, order_id: int,
                 order_in: OrderUpdate) -> OrderPublic:
    """Update an existing order"""
    logger.info(f"User {current_user.username} updating order {order_id}")

    # Get the order
    order = session.get(Order, order_id)
    if not order:
        logger.warning(f"Order not found: {order_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Order not found")
    try:
        # Update basic order fields
        update_data = order_in.model_dump(exclude={"items"}, exclude_unset=True)
        for field, value in update_data.items():
            setattr(order, field, value)

        # Update item variants if provided
        if order_in.items:
            # Get existing links as a dict for easy lookup
            existing_links = {
                link.item_variant_id: link for link in order.item_links
            }
            updated_variant_ids = set()
            for item in order_in.items:
                variant_id = item.item_variant_id
                updated_variant_ids.add(variant_id)

                if variant_id in existing_links:
                    # Update existing link
                    link = existing_links[variant_id]
                    item_data = item.model_dump(exclude={"item_id"},
                                                exclude_unset=True)
                    for field, value in item_data.items():
                        setattr(link, field, value)
                else:
                    # Create new link
                    new_link = OrderItemLink(order_id=order.id,
                                             item_variant_id=variant_id,
                                             quantity=item.quantity,
                                             price=item.price)
                    session.add(new_link)

            # Remove links that are no longer in the update
            for old_variant_id in set(
                    existing_links.keys()) - updated_variant_ids:
                session.delete(existing_links[old_variant_id])

        # Update timestamp
        order.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(order)  # Reload relationships

        logger.info(f"Order {order_id} updated successfully")
        return transform_order_to_public(order)

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update order {order_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to update order")


@router.delete("/{order_id}",
               status_code=status.HTTP_200_OK,
               summary="Delete order",
               description="Delete an order by ID (superuser only)")
def delete_order(session: SessionDep, current_user: CurrentUser, order_id: int):
    """Delete an order (superuser only)"""
    logger.debug(
        f"User {current_user.username} attempting to delete order {order_id}")

    # Check permissions
    if not current_user.is_superuser:
        logger.warning(
            f"Permission denied: {current_user.username} tried to delete order {order_id}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only superusers can delete orders")

    # Get the order
    order = session.get(Order, order_id)
    if not order:
        logger.warning(f"Order not found for deletion: {order_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Order not found")

    try:
        session.delete(order)
        session.commit()

        logger.info(
            f"Order {order_id} deleted successfully by {current_user.username}")
        return {"message": f"Order {order_id} deleted successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete order {order_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to delete order")
