from uuid import UUID
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Query, Response
from sqlmodel import select

# --- Project Imports ---
from core.logger import logger
from core.query_utils import *
from core.exceptions import *
from core.dependencies import CurrentUser
from core.database import SessionDep
from core.models import (
    ItemVariant,
    ItemVariantPublic,
    ItemVariantFilters,
    ItemVariantUpdate,
)

router = APIRouter(prefix="/variants", tags=["Items"])


def _apply_filters(stmt, filters: ItemVariantFilters):
    """Apply filters to query statement"""
    if filters.id:
        stmt = stmt.where(ItemVariant.id.in_(filters.id))
    if filters.item_id:
        stmt = stmt.where(ItemVariant.item_id.in_(filters.item_id))
    if filters.color:
        stmt = stmt.where(ItemVariant.color == filters.color)
    if filters.size:
        stmt = stmt.where(ItemVariant.size == filters.size)
    if filters.status:
        stmt = stmt.where(ItemVariant.status.in_(filters.status))
    if filters.service_end_time:
        stmt = stmt.where(
            ItemVariant.service_end_time == filters.service_end_time)
    if filters.service_start_time:
        stmt = stmt.where(
            ItemVariant.service_start_time == filters.service_start_time)

    return stmt.distinct()


@router.get("",
            response_model=List[ItemVariantPublic],
            summary="List of item variants",
            description="Retrieve a list of all item variants.")
async def read_variants(
    response: Response,
    session: SessionDep,
    current_user: CurrentUser,
    filter_: str = Query("{}", alias="filter"),
    range_: str = Query("[0, 500]", alias="range"),
    sort: str = Query('["id","ASC"]', alias="sort")
) -> List[ItemVariantPublic]:
    try:
        # Parse inputs
        filter_dict, range_list, sort_field, sort_order = parse_query_params(
            filter_, range_, sort)

        # Build filters and pagination
        filters = ItemVariantFilters(**filter_dict)
        offset, limit = calculate_pagination(range_list)

        # Build base query
        stmt = select(ItemVariant)
        stmt = _apply_filters(stmt, filters)
        stmt = apply_sorting(stmt, ItemVariant, sort_field, sort_order)

        # Get total count before pagination
        total = get_total_count(session, stmt)

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)
        variants = session.exec(stmt).all()

        result = [ItemVariantPublic.model_validate(v) for v in variants]

        set_pagination_headers(response, offset, len(result), total)
        logger.info(
            f"Fetched {len(variants)} variants out of {total} total for user {current_user.username}"
        )
        return result

    except Exception as e:
        logger.error(f"Error fetching variants: {e}")
        raise InternalErrorException("Failed to retrieve variants")


@router.get("/{variant_id}",
            response_model=ItemVariantPublic,
            summary="Get item variant by ID",
            description="Fetch a single itemvariant  by its unique ID.")
def read_variant(session: SessionDep, current_user: CurrentUser,
                 variant_id: UUID) -> ItemVariantPublic:
    logger.debug(
        f"User {current_user.username} fetching item variant: {variant_id}")

    variant = session.get(ItemVariant, variant_id)
    if not variant:
        logger.warning(f"Item variant not found: {variant_id}")
        raise NotFoundException("Item variant not found")

    logger.info(f"Item variant retrieved: {variant.id}")
    return ItemVariantPublic.model_validate(variant)


@router.put("/{variant_id}",
            response_model=ItemVariantPublic,
            summary="Update item variant",
            description="Update an existing variant by ID.")
def update_variant(session: SessionDep, current_user: CurrentUser,
                   variant_id: UUID,
                   variant_in: ItemVariantUpdate) -> ItemVariantPublic:
    logger.info(f"User {current_user.username} updating variant {variant_id}")

    variant = session.get(ItemVariant, variant_id)
    if not variant:
        logger.warning(f"Variant with ID {variant_id} not found")
        raise NotFoundException("Item variant not found")

    # Validate update data
    update_data = variant_in.model_dump(exclude_unset=True)
    if not update_data:
        logger.info(f"No changes provided for variant with ID: {id}")
        raise BadRequestException("No data provided for update")
    try:
        # Apply updates
        for field, value in update_data.items():
            setattr(variant, field, value)

        variant.updated_at = datetime.now(timezone.utc)
        if variant.status == "available":
            variant.service_start_time = None
            variant.service_end_time = None

        session.add(variant)
        session.commit()
        session.refresh(variant)

        logger.info(f"Updated variant: {variant_id}")
        return ItemVariantPublic.model_validate(variant)

    except Exception as e:
        session.rollback()
        logger.error(f"Error updating variant {variant_id}: {e}")
        raise InternalErrorException("Failed to update item variant")
