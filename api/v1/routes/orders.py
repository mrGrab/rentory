from typing import List
from fastapi import APIRouter, Response, status, Depends, Query

# --- Project Imports ---
from services.order_service import OrderService
from core.logger import logger
from core.dependencies import CurrentUser
from core.database import SessionDep
from core.exceptions import NotFoundException
from core.query_utils import parse_params, calculate_pagination, set_pagination_headers
from models.payment import PaymentPublic
from models.order import (
    Order,
    OrderPublic,
    OrderCreate,
    OrderFilters,
    OrderUpdate,
    OrderItemPublicInfo,
)

router = APIRouter(prefix="/orders", tags=["Orders"])

# ---------- Helper Functions ----------


def get_order_service(session: SessionDep) -> OrderService:
    """Dependency to get OrderService instance"""
    return OrderService(session)


def get_order_or_404(
    order_id: int,
    service: OrderService = Depends(get_order_service)) -> Order:
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
        item_info = OrderItemPublicInfo(item_id=variant.item_id,
                                        item_variant_id=link.item_variant_id,
                                        title=variant.item.title,
                                        size=variant.size,
                                        color=variant.color,
                                        quantity=link.quantity,
                                        price=link.price,
                                        deposit=link.deposit)
        items.append(item_info)

    # Transform payments
    payments = [
        PaymentPublic.model_validate(payment) for payment in order.payments
    ]

    return OrderPublic.model_validate(order,
                                      update={
                                          "items": items,
                                          "payments": payments
                                      })


# ---------- Route Handlers ----------


@router.get("",
            response_model=List[OrderPublic],
            summary="List orders with pagination")
def list_orders(response: Response,
                current_user: CurrentUser,
                service: OrderService = Depends(get_order_service),
                filter_: str = Query("{}", alias="filter"),
                range_: str = Query("[0, 500]", alias="range"),
                sort: str = Query('["created_at", "DESC"]', alias="sort")):
    """List orders with filtering, sorting, and pagination"""

    logger.debug(f"User {current_user.username} listing orders")

    # Parse query parameters
    params = parse_params(filter_, range_, sort)
    filters = OrderFilters(**params.filters)
    offset, limit = calculate_pagination(params.range_list)

    # Fetch orders
    orders, total = service.get_orders(filters=filters,
                                       offset=offset,
                                       limit=limit,
                                       sort_field=params.sort_field,
                                       sort_order=params.sort_order)

    # Transform to public schema
    result = [to_public(order) for order in orders]

    # Set pagination headers
    set_pagination_headers(response=response,
                           count=len(result),
                           total=total,
                           offset=offset,
                           resource_name="orders")

    logger.info(
        f"User {current_user.username} retrieved {len(result)}/{total} orders")
    return result


@router.post("",
             response_model=OrderPublic,
             status_code=status.HTTP_201_CREATED,
             summary="Create a new order",
             description="Create a new order and link it to item variants")
def create_order(order_in: OrderCreate,
                 current_user: CurrentUser,
                 service: OrderService = Depends(get_order_service)):
    """Create a new order"""
    logger.debug(f"User {current_user.username} creating new order")

    if not order_in.created_by_user_id:
        order_in.created_by_user_id == current_user.id
    order = service.create(order_in)

    logger.info(f"User {current_user.username} created order {order.id}")
    return to_public(order)


@router.get("/{order_id}",
            response_model=OrderPublic,
            summary="Get order by ID",
            description="Retrieve details of a specific order by its ID")
def get_order(current_user: CurrentUser,
              order: Order = Depends(get_order_or_404)):
    """Get a specific order by ID"""
    logger.debug(f"User {current_user.username} fetching order {order.id}")
    return to_public(order)


@router.put("/{order_id}",
            response_model=OrderPublic,
            summary="Update order",
            description="Update an existing order by its ID")
def update_order(order_in: OrderUpdate,
                 current_user: CurrentUser,
                 order: Order = Depends(get_order_or_404),
                 service: OrderService = Depends(get_order_service)):
    """Update an existing order"""
    logger.info(f"User {current_user.username} updating order {order.id}")

    updated_order = service.update(order, order_in)

    logger.info(f"User {current_user.username} updated order {order.id}")
    return to_public(updated_order)


@router.delete("/{order_id}",
               status_code=status.HTTP_200_OK,
               summary="Delete order",
               description="Delete an order by ID (superuser only)")
def delete_order(current_user: CurrentUser,
                 order: Order = Depends(get_order_or_404),
                 service: OrderService = Depends(get_order_service)):
    """Delete an order (superuser only)"""
    logger.debug(f"User {current_user.username} deleting order {order.id}")

    service.archive(order)

    logger.info(f"Order {order.id} deleted by {current_user.username}")
    return {"message": f"Order {order.id} deleted successfully"}
