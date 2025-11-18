from uuid import UUID
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Query, status, Response, Depends

# --- Project Imports ---
from core.logger import logger
from core.database import SessionDep
from core.dependencies import CurrentUser
from core.exceptions import NotFoundException
from core.query_utils import parse_params, calculate_pagination, set_pagination_headers
from services.item_service import ItemService
from models.item_variant import ItemVariantPublicInternal, ItemVariant
from models.item import Item, ItemFilters, ItemPublic, ItemCreate, ItemUpdate

router = APIRouter(prefix="/items", tags=["Items"])

# ---------- Helper Functions ----------


def get_item_service(session: SessionDep) -> ItemService:
    """Dependency to get ItemService instance"""
    return ItemService(session)


def get_item_or_404(
    item_id: UUID, service: ItemService = Depends(get_item_service)) -> Item:
    """Dependency to retrieve an item by ID or raise NotFoundException"""
    item = service.get_by_id(item_id)
    if not item:
        logger.warning(f"Item not found: {item_id}")
        raise NotFoundException(f"Item with ID {item_id} not found")
    return item


def to_public(item: Item) -> ItemPublic:
    """Convert Item to ItemPublic with variant and order information"""
    order_ids = set()
    public_variants = []

    for variant in item.variants:
        if not variant.is_archived:
            public_variants.append(
                ItemVariantPublicInternal.model_validate(variant))
        for link in variant.order_links:
            order_ids.add(link.order_id)
    return ItemPublic.model_validate(item,
                                     update={
                                         "order_ids": list(order_ids),
                                         "variants": public_variants
                                     })


# ---------- Dropdown Endpoints ----------
@router.get("/categories",
            response_model=List[str],
            summary="Get category options")
def get_categories(current_user: CurrentUser,
                   service: ItemService = Depends(get_item_service)):
    """Get distinct category values for dropdown"""
    logger.debug(f"User {current_user.username} fetching category options")
    return service.get_distinct_field_values(Item, "category")


@router.get("/statuses",
            response_model=List[str],
            summary="Get status options")
def get_statuses(current_user: CurrentUser,
                 service: ItemService = Depends(get_item_service)):
    """Get distinct status values for dropdown"""
    logger.debug(f"User {current_user.username} fetching status options")
    return service.get_distinct_field_values(Item, "status")


@router.get("/sizes", response_model=List[str], summary="Get size options")
def get_sizes(current_user: CurrentUser,
              service: ItemService = Depends(get_item_service)):
    """Get distinct size values for dropdown"""
    logger.debug(f"User {current_user.username} fetching size options")
    return service.get_distinct_field_values(ItemVariant, "size")


@router.get("/colors", response_model=List[str], summary="Get color options")
def get_colors(current_user: CurrentUser,
               service: ItemService = Depends(get_item_service)):
    """Get distinct color values for dropdown"""
    logger.debug(f"User {current_user.username} fetching color options")
    return service.get_distinct_field_values(ItemVariant, "color")


@router.get("/variant-statuses",
            response_model=List[str],
            summary="Get variant status options")
def get_variant_statuses(current_user: CurrentUser,
                         service: ItemService = Depends(get_item_service)):
    """Get distinct variant status values for dropdown"""
    logger.debug(
        f"User {current_user.username} fetching variant status options")
    return service.get_distinct_field_values(ItemVariant, "status")


# ---------- CRUD Endpoints ----------


@router.get("",
            response_model=List[ItemPublic],
            summary="List items with pagination",
            description="Retrieve a paginated list of items")
def list_items(response: Response,
               current_user: CurrentUser,
               service: ItemService = Depends(get_item_service),
               filter_: str = Query("{}", alias="filter"),
               range_: str = Query("[0, 500]", alias="range"),
               sort: str = Query('["id","DESC"]', alias="sort")):

    logger.debug(f"User {current_user.username} listing items")

    # Parse query parameters
    params = parse_params(filter_, range_, sort)
    filters = ItemFilters(**params.filters)
    offset, limit = calculate_pagination(params.range_list)

    # Fetch items
    items, total = service.get_items(filters=filters,
                                     offset=offset,
                                     limit=limit,
                                     sort_field=params.sort_field,
                                     sort_order=params.sort_order)

    # Convert to public schema
    result = [to_public(item) for item in items]

    # Set pagination headers
    set_pagination_headers(response=response,
                           count=len(result),
                           total=total,
                           offset=offset,
                           resource_name="items")

    logger.info(
        f"User {current_user.username} retrieved {len(result)}/{total} items")
    return result


@router.post("",
             response_model=ItemPublic,
             status_code=status.HTTP_201_CREATED,
             summary="Create new item",
             description="Create a new item with variants and prices")
def create_item(item_in: ItemCreate,
                current_user: CurrentUser,
                service: ItemService = Depends(get_item_service)):

    logger.info(
        f"User {current_user.username} creating item '{item_in.title}'")

    item = service.create(item_in)

    logger.info(f"User {current_user.username} created item {item.id}")
    return to_public(item)


@router.get("/{item_id}",
            response_model=ItemPublic,
            summary="Get item by ID",
            description="Retrieve a specific item by its ID")
def get_item(current_user: CurrentUser, item: Item = Depends(get_item_or_404)):
    logger.info(f"User {current_user.username} retrieved item {item.id}")
    return to_public(item)


@router.get("/{item_id}/availability",
            response_model=ItemPublic,
            summary="Check item availability",
            description="Get item with availability status")
def check_availability(current_user: CurrentUser,
                       item: Item = Depends(get_item_or_404),
                       service: ItemService = Depends(get_item_service),
                       start_time: Optional[date] = None,
                       end_time: Optional[date] = None,
                       exclude_order_id: Optional[int] = None):
    logger.debug(
        f"User {current_user.username} checking availability for item {item.id}"
    )

    # Check availability if time range is provided
    if start_time and end_time:
        item = service.check_availability(item, start_time, end_time,
                                          exclude_order_id)

    logger.info(f"Availability checked for item {item.id}")
    return to_public(item)


@router.put("/{item_id}",
            response_model=ItemPublic,
            summary="Update item",
            description="Update an existing item")
def update_item(item_in: ItemUpdate,
                current_user: CurrentUser,
                item: Item = Depends(get_item_or_404),
                service: ItemService = Depends(get_item_service)):
    logger.info(f"User {current_user.username} updating item {item.id}")

    updated_item = service.update(item, item_in)

    logger.info(f"User {current_user.username} updated item {item.id}")
    return to_public(updated_item)


@router.delete("/{item_id}",
               status_code=status.HTTP_200_OK,
               summary="Delete item",
               description="Delete an item by ID")
def delete_item(current_user: CurrentUser,
                item: Item = Depends(get_item_or_404),
                service: ItemService = Depends(get_item_service)):
    """Delete an item"""
    logger.info(f"User {current_user.username} deleting item {item.id}")

    service.delete(item)

    logger.info(f"User {current_user.username} deleted item {item.id}")
    return {"message": f"Item {item.id} deleted successfully"}
