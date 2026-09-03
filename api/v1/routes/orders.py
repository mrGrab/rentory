from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse

from core.database import SessionDep
from core.dependencies import CurrentSuperuser, CurrentUser
from core.exceptions import NotFoundException
from core.logger import logger
from core.query_utils import calculate_pagination, parse_params, set_pagination_headers
from models.order import (
    Order,
    OrderCreate,
    OrderFilters,
    OrderItemPublicInfo,
    OrderPublic,
    OrderUpdate,
)
from models.payment import PaymentPublic
from services.helpers import display_color, display_size, display_title
from services.invoice import generate_invoice_jpeg as invoice_generate_jpeg
from services.invoice import generate_invoice_pdf
from services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])

# ---------- Helper Functions ----------


def get_order_service(session: SessionDep) -> OrderService:
    """Dependency to get OrderService instance"""
    return OrderService(session)


def get_order_or_404(
    order_id: int, service: Annotated[OrderService, Depends(get_order_service)]
) -> Order:
    """Dependency to retrieve an order by ID or raise NotFoundException"""
    order = service.get_by_id(order_id)
    if not order:
        logger.warning(f"Order not found: {order_id}")
        raise NotFoundException(f"Order with ID {order_id} not found")
    return order


def to_public(order: Order) -> OrderPublic:
    """Convert Order to OrderPublic with full item and payment information"""
    # Transform order items
    items = []
    for link in order.item_links:
        variant = link.item_variant
        if variant is None or variant.item is None:
            raise NotFoundException("Order has an invalid item variant link")
        item_info = OrderItemPublicInfo(
            item_id=variant.item_id,
            item_variant_id=link.item_variant_id,
            title=display_title(link.item_title_snapshot, variant.item.title),
            size=display_size(link.variant_size_snapshot, variant.size),
            color=display_color(link.variant_color_snapshot, variant.color),
            quantity=link.quantity,
            price=link.price,
            deposit=link.deposit,
            item_title_snapshot=link.item_title_snapshot,
            variant_size_snapshot=link.variant_size_snapshot,
            variant_color_snapshot=link.variant_color_snapshot,
            price_type_snapshot=link.price_type_snapshot,
        )
        items.append(item_info)

    # Transform payments
    payments = [PaymentPublic.model_validate(payment) for payment in order.payments]

    return OrderPublic.model_validate(
        order, update={"items": items, "payments": payments}
    )


# ---------- Route Handlers ----------


@router.get("", response_model=list[OrderPublic], summary="List orders with pagination")
def list_orders(
    response: Response,
    current_user: CurrentUser,
    service: Annotated[OrderService, Depends(get_order_service)],
    filter_: Annotated[str, Query(alias="filter")] = "{}",
    range_: Annotated[str, Query(alias="range")] = "[0, 500]",
    sort: Annotated[str, Query(alias="sort")] = '["created_at", "DESC"]',
):
    """List orders with filtering, sorting, and pagination"""

    logger.debug(f"User {current_user.username} listing orders")

    # Parse query parameters
    params = parse_params(filter_, range_, sort)
    filters = OrderFilters(**params.filters)
    offset, limit = calculate_pagination(params.range_list)

    # Fetch orders
    orders, total = service.get_orders(
        filters=filters,
        offset=offset,
        limit=limit,
        sort_field=params.sort_field,
        sort_order=params.sort_order,
    )

    # Transform to public schema
    result = [to_public(order) for order in orders]

    # Set pagination headers
    set_pagination_headers(
        response=response,
        count=len(result),
        total=total,
        offset=offset,
        resource_name="orders",
    )

    logger.info(f"User {current_user.username} retrieved {len(result)}/{total} orders")
    return result


@router.post(
    "",
    response_model=OrderPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
    description="Create a new order and link it to item variants",
)
def create_order(
    order_in: OrderCreate,
    current_user: CurrentUser,
    service: Annotated[OrderService, Depends(get_order_service)],
):
    """Create a new order"""
    logger.debug(f"User {current_user.username} creating new order")

    if not order_in.created_by_user_id:
        order_in.created_by_user_id = current_user.id
    order = service.create(order_in)

    logger.info(f"User {current_user.username} created order {order.id}")
    return to_public(order)


@router.get(
    "/{order_id}/invoice",
    summary="Generate invoice PDF",
    description="Generate and download invoice PDF for an order",
)
def generate_invoice(
    current_user: CurrentUser,
    order: Annotated[Order, Depends(get_order_or_404)],
):
    """Generate invoice PDF for an order"""
    logger.debug(
        f"User {current_user.username} generating invoice for order {order.id}"
    )

    pdf_bytes = generate_invoice_pdf(order)

    logger.info(f"Invoice generated for order {order.id}")

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{order.id}.pdf"},
    )


@router.get(
    "/{order_id}/invoice/jpeg",
    summary="Generate invoice JPEG",
    description="Generate and download the complete invoice as one tall JPEG",
)
def generate_invoice_jpeg(
    current_user: CurrentUser,
    order: Annotated[Order, Depends(get_order_or_404)],
):
    """Generate a complete invoice JPEG for an order."""
    logger.debug(
        f"User {current_user.username} generating invoice JPEG for order {order.id}"
    )

    jpeg_bytes = invoice_generate_jpeg(order)

    logger.info(f"Invoice JPEG generated for order {order.id}")

    return StreamingResponse(
        BytesIO(jpeg_bytes),
        media_type="image/jpeg",
        headers={"Content-Disposition": f"attachment; filename=invoice_{order.id}.jpg"},
    )


@router.get(
    "/{order_id}",
    response_model=OrderPublic,
    summary="Get order by ID",
    description="Retrieve details of a specific order by its ID",
)
def get_order(
    current_user: CurrentUser, order: Annotated[Order, Depends(get_order_or_404)]
):
    """Get a specific order by ID"""
    logger.debug(f"User {current_user.username} fetching order {order.id}")
    return to_public(order)


@router.put(
    "/{order_id}",
    response_model=OrderPublic,
    summary="Update order",
    description="Update an existing order by its ID",
)
def update_order(
    order_in: OrderUpdate,
    current_user: CurrentUser,
    order: Annotated[Order, Depends(get_order_or_404)],
    service: Annotated[OrderService, Depends(get_order_service)],
):
    """Update an existing order"""
    logger.info(f"User {current_user.username} updating order {order.id}")

    updated_order = service.update(order, order_in)

    logger.info(f"User {current_user.username} updated order {order.id}")
    return to_public(updated_order)


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete order",
    description="Delete an order by ID (superuser only)",
)
def delete_order(
    current_user: CurrentSuperuser,
    order: Annotated[Order, Depends(get_order_or_404)],
    service: Annotated[OrderService, Depends(get_order_service)],
):
    """Delete an order (superuser only)"""
    logger.debug(f"User {current_user.username} deleting order {order.id}")

    service.archive(order)

    logger.info(f"Order {order.id} deleted by {current_user.username}")
    return {"message": f"Order {order.id} deleted successfully"}
