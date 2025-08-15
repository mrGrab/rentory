from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query, status, Response
from typing import Optional, List, cast
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from sqlmodel import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import asc, desc
from core.logger import logger
from core.dependency import (
    SessionDep,
    get_current_user,
    get_current_superuser,
    save_to_db,
    CurrentUser,
    calculate_pagination,
)
from core.models import Client, ClientCreate, ClientPublic, ClientFilters, ClientUpdate
from fastapi.encoders import jsonable_encoder
import json

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.post("",
             response_model=ClientPublic,
             summary="Create a new client",
             description="Adds a new client to the system.",
             dependencies=[Depends(get_current_user)])
def create_client(session: SessionDep, client_in: ClientCreate):
    logger.debug(f"Creating new client with phone='{client_in.phone}'")
    now = datetime.now(timezone.utc)

    client = Client(**client_in.model_dump(exclude_unset=True),
                    created_at=now,
                    updated_at=now)
    try:
        session.add(client)
        session.commit()
        session.refresh(client)
        logger.info(f"Client created successfully: {client.id}")
        return ClientPublic(**client.model_dump())
    except IntegrityError as ie:
        session.rollback()
        error_msg = str(ie.orig).lower() if ie.orig else str(ie).lower()
        if "unique constraint" in error_msg or "duplicate" in error_msg:
            detail = "A client with the same phone or email already exists."
            logger.warning(f"Unique constraint violation: {detail}")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=detail)
        raise
    except Exception as e:
        session.rollback()
        logger.exception(f"Unexpected error while creating client: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create client")


@router.get("",
            summary="Client list",
            description="Retrieve a paginated list of available clients.",
            dependencies=[Depends(get_current_user)],
            response_model=List[ClientPublic])
async def read_clients(response: Response,
                       session: SessionDep,
                       filter_: str = Query("{}", alias="filter"),
                       range_: str = Query("[0, 500]", alias="range"),
                       sort: str = Query('["id", "ASC"]', alias="sort")):
    try:
        stmt = select(Client)

        # Parse query params
        sort_field, sort_order = json.loads(sort)
        offset, limit = calculate_pagination(json.loads(range_))
        filter_dict = json.loads(filter_)
        filters = ClientFilters(**filter_dict)

        # Apply filters
        filter_map = {
            "id": lambda v: Client.id.in_(v),
            "phone": lambda v: Client.phone.ilike(f"%{v}%"),
            "instagram": lambda v: Client.instagram.ilike(f"%{v}%"),
            "email": lambda v: Client.email.ilike(f"%{v}%"),
            "given_name": lambda v: Client.given_name.ilike(f"%{v}%"),
            "surname": lambda v: Client.surname.ilike(f"%{v}%"),
            "discount": lambda v: Client.discount == v,
        }
        for field, condition in filter_map.items():
            value = getattr(filters, field)
            if value:
                stmt = stmt.where(condition(value))

        # Apply sorting
        sort_column = getattr(Client, sort_field)
        if sort_order.upper() == "ASC":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

        # Count total records
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = session.exec(count_stmt).one()

        # Apply pagination and fetch results
        stmt = stmt.offset(offset).limit(limit)
        clients = session.exec(stmt).all()

        # Serialize and prepare response
        result = []
        for client in clients:
            order_ids = [order.id for order in client.orders]
            result.append(
                ClientPublic(**client.model_dump(), order_ids=order_ids))
        content_range = f"items {offset}-{offset + len(result) - 1}/{total}"
        response.headers.update({
            "Content-Range": content_range,
            "X-Total-Count": str(total),
            "Access-Control-Expose-Headers": "Content-Range, X-Total-Count",
            "Content-Type": "application/json",
        })

        logger.info(f"Fetched {len(result)} clients out of {total} total")
        return result

    except Exception as e:
        logger.exception("Error fetching clients")
        raise HTTPException(status_code=500,
                            detail="Failed to retrieve clients")


@router.get("/{id}",
            response_model=ClientPublic,
            summary="Get client by ID",
            description="Fetch a single client by its unique ID.",
            dependencies=[Depends(get_current_user)])
def get_client_by_id(session: SessionDep, id: UUID) -> ClientPublic:
    logger.debug(f"Fetching client with ID: {id}")
    try:
        client = session.get(Client, id)
        if not client:
            logger.warning(f"Client not found: {id}")
            raise HTTPException(status_code=404, detail="Client not found")
        logger.info(f"Client retrieved: {client.id}")
        order_ids = [order.id for order in client.orders]
        return ClientPublic(**client.model_dump(), order_ids=order_ids)
    except Exception as e:
        logger.exception(f"Failed to retrieve client with ID {id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve client")


@router.put("/{id}",
            response_model=ClientPublic,
            summary="Update client by ID",
            description="Update an existing client's details by its unique ID.",
            dependencies=[Depends(get_current_superuser)])
def update_client(session: SessionDep, id: UUID, client_in: ClientUpdate):
    logger.debug(f"Attempting to update client with ID: {id}")

    client = session.get(Client, id)
    if not client:
        logger.warning(f"Client with ID {id} not found")
        raise HTTPException(status_code=404, detail="Client not found")

    update_data = client_in.model_dump(exclude_unset=True)
    if not update_data:
        logger.info(f"No changes provided for client with ID: {id}")
        raise HTTPException(status_code=400,
                            detail="No data provided for update")
    try:
        for field, value in update_data.items():
            setattr(client, field, value)

        client.updated_at = datetime.now(timezone.utc)

        session.add(client)
        session.commit()
        session.refresh(client)

        logger.info(f"Client updated successfully: {client.id}")
        order_ids = [order.id for order in client.orders]
        return ClientPublic(**client.model_dump(), order_ids=order_ids)

    except Exception as e:
        logger.exception(f"Failed to update client with ID {id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update client")
