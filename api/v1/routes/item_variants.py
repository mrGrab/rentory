from uuid import UUID
from typing import List
from fastapi import APIRouter, Query, Response, Depends

# --- Project Imports ---
from core.logger import logger
from core.dependencies import CurrentUser
from core.database import SessionDep
from core.exceptions import NotFoundException
from services.item_variant_service import ItemVariantService
from core.query_utils import parse_params, calculate_pagination, set_pagination_headers
from models.item_variant import (
    ItemVariant,
    ItemVariantPublic,
    ItemVariantFilters,
    ItemVariantUpdate,
)

router = APIRouter(prefix="/variants", tags=["Item Variants"])

# ---------- Helper Functions ----------


def get_variant_service(session: SessionDep) -> ItemVariantService:
    """Dependency to get ItemVariantService instance"""
    return ItemVariantService(session)


def get_variant_or_404(
    variant_id: UUID,
    service: ItemVariantService = Depends(get_variant_service)
) -> ItemVariant:
    """Dependency to retrieve a variant by ID or raise NotFoundException"""
    variant = service.get_by_id(variant_id)
    if not variant:
        logger.warning(f"Item variant not found: {variant_id}")
        raise NotFoundException(f"Item variant with ID {variant_id} not found")
    return variant


# ---------- Routes ----------


@router.get("",
            response_model=List[ItemVariantPublic],
            summary="List of item variants",
            description="Retrieve a list of all item variants")
def list_variants(response: Response,
                  current_user: CurrentUser,
                  service: ItemVariantService = Depends(get_variant_service),
                  filter_: str = Query("{}", alias="filter"),
                  range_: str = Query("[0, 500]", alias="range"),
                  sort: str = Query('["id","ASC"]', alias="sort")):
    logger.debug(f"User {current_user.username} listing variants")

    # Parse query parameters
    params = parse_params(filter_, range_, sort)
    filters = ItemVariantFilters(**params.filters)
    offset, limit = calculate_pagination(params.range_list)

    # Fetch variants
    variants, total = service.get_variants(filters=filters,
                                           offset=offset,
                                           limit=limit,
                                           sort_field=params.sort_field,
                                           sort_order=params.sort_order)

    # Set pagination headers
    set_pagination_headers(response=response,
                           count=len(variants),
                           total=total,
                           offset=offset,
                           resource_name="variants")

    logger.info(
        f"User {current_user.username} retrieved {len(variants)}/{total} variants"
    )
    return variants


@router.get("/{variant_id}",
            response_model=ItemVariantPublic,
            summary="Get item variant by ID",
            description="Retrieve a specific item variant by its UUID")
def get_variant(current_user: CurrentUser,
                variant: ItemVariant = Depends(get_variant_or_404)):
    logger.info(f"User {current_user.username} retrieved variant {variant.id}")
    return variant


@router.put("/{variant_id}",
            response_model=ItemVariantPublic,
            summary="Update item variant",
            description="Update an existing variant by ID")
def update_variant(current_user: CurrentUser,
                   variant_in: ItemVariantUpdate,
                   variant: ItemVariant = Depends(get_variant_or_404),
                   service: ItemVariantService = Depends(get_variant_service)):
    logger.info(f"User {current_user.username} updating variant {variant.id}")

    updated_variant = service.update(variant, variant_in)

    logger.info(f"User {current_user.username} updated variant {variant.id}")
    return updated_variant
