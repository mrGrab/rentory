import json
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from sqlmodel import select, func
from core.logger import logger
from core.dependency import (
    SessionDep,
    get_current_user,
    calculate_pagination,
    apply_sorting,
    get_total_count,
    set_pagination_headers,
)
from core.models import (
    ItemVariant,
    ItemVariantPublic,
    ItemVariantFilters,
    ItemVariantUpdate,
)

router = APIRouter(prefix="/variants", tags=["Items"])


def _apply_filters(stmt, f: ItemVariantFilters):
    """Apply all filters to the query statement."""

    if f.id:
        stmt = stmt.where(ItemVariant.id.in_(f.id))
    if f.item_id:
        stmt = stmt.where(ItemVariant.item_id.in_(f.item_id))
    if f.color:
        stmt = stmt.where(ItemVariant.color == f.color)
    if f.size:
        stmt = stmt.where(ItemVariant.size == f.size)
    if f.status:
        stmt = stmt.where(ItemVariant.status.in_(f.status))
    if f.service_end_time:
        stmt = stmt.where(ItemVariant.service_end_time == f.service_end_time)
    if f.service_start_time:
        stmt = stmt.where(
            ItemVariant.service_start_time == f.service_start_time)

    return stmt.distinct()


@router.get("",
            summary="List of item variants",
            description="Retrieve a list of all item variants.",
            dependencies=[Depends(get_current_user)])
async def read_variants(response: Response,
                        session: SessionDep,
                        filter_: str = Query("{}", alias="filter"),
                        range_: str = Query("[0, 500]", alias="range"),
                        sort: str = Query('["id","ASC"]', alias="sort")):
    try:
        # Parse inputs
        sort_field, sort_order = json.loads(sort)
        offset, limit = calculate_pagination(json.loads(range_))
        filter_dict = json.loads(filter_)
        filters = ItemVariantFilters(**filter_dict)

        stmt = select(ItemVariant)

        # Apply filters
        stmt = _apply_filters(stmt, filters)

        # Apply sorting
        stmt = apply_sorting(stmt, ItemVariant, sort_field, sort_order)

        # Get total count before pagination
        total = get_total_count(session, stmt)

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)
        variants = session.exec(stmt).all()

        result = [ItemVariantPublic.model_validate(v) for v in variants]

        set_pagination_headers(response, offset, len(result), total)
        logger.info(f"Fetched {len(variants)} variants out of {total} total")
        return result

    except Exception as e:
        logger.error(f"Error fetching variants: {e}")
        raise HTTPException(status_code=500,
                            detail="Failed to retrieve variants")


@router.get("/{id}",
            response_model=ItemVariantPublic,
            summary="Get item variant by ID",
            description="Fetch a single itemvariant  by its unique ID.",
            dependencies=[Depends(get_current_user)])
def read_variant(session: SessionDep, id: UUID) -> ItemVariantPublic:
    logger.debug(f"Fetching item variant with ID: {id}")

    stmt = select(ItemVariant).where(ItemVariant.id == id)

    variant = session.exec(stmt).first()
    if not variant:
        logger.warning(f"Item variant not found: {id}")
        raise HTTPException(status_code=404, detail="Item variant not found")

    logger.info(f"Item variant retrieved: {variant.id}")
    return variant


@router.put("/{id}",
            response_model=ItemVariantPublic,
            summary="Update item variant by ID",
            description="Update an existing variant details by its unique ID.",
            dependencies=[Depends(get_current_user)])
def update_variant(session: SessionDep, id: UUID,
                   variant_in: ItemVariantUpdate):
    logger.info(f"Updating variant ID {id}")

    stmt = select(ItemVariant).where(ItemVariant.id == id)
    variant = session.exec(stmt).one_or_none()
    if not variant:
        logger.warning(f"Item variant with ID {id} not found")
        raise HTTPException(status_code=404, detail="Item variant not found")
    try:
        update_data = variant_in.model_dump(exclude_unset=True)
        if not update_data:
            logger.info(f"No changes provided for variant with ID: {id}")
            raise HTTPException(status_code=400,
                                detail="No data provided for update")

        for field, value in update_data.items():
            setattr(variant, field, value)

        variant.updated_at = datetime.now(timezone.utc)
        if variant.status == "available":
            variant.service_start_time = None
            variant.service_end_time = None

        session.add(variant)
        session.commit()
        session.refresh(variant)

        logger.info(f"Item variant updated successfully: {variant.id}")
        return ItemVariantPublic.model_validate(variant)

    except Exception as e:
        logger.exception(f"Failed to update item variant ID {id}: {e}")
        raise HTTPException(status_code=500,
                            detail="Failed to update item variant")
