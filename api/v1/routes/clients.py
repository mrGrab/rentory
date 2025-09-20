from uuid import UUID
from typing import List
from sqlmodel import select, func
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, status, Response

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
    Client,
    ClientCreate,
    ClientPublic,
    ClientFilters,
    ClientUpdate,
    Order,
)

router = APIRouter(prefix="/clients", tags=["Clients"])


def apply_client_filters(stmt, filters: ClientFilters):
    """Apply filters to client query"""
    if filters.id:
        stmt = stmt.where(Client.id.in_(filters.id))
    if filters.phone:
        stmt = stmt.where(Client.phone.ilike(f"%{filters.phone}%"))
    if filters.email:
        stmt = stmt.where(Client.email == filters.email)
    if filters.instagram:
        stmt = stmt.where(Client.instagram == filters.instagram)
    if filters.given_name:
        stmt = stmt.where(Client.given_name == filters.given_name)
    if filters.surname:
        stmt = stmt.where(Client.surname == filters.surname)
    if filters.discount is not None:
        stmt = stmt.where(Client.discount == filters.discount)

    return stmt.distinct()


def transform_client_to_public(client: Client) -> ClientPublic:
    """Convert Client to ClientPublic with order IDs"""
    order_ids = [order.id for order in client.orders] if client.orders else []
    return ClientPublic(**client.model_dump(), order_ids=order_ids)


@router.get("",
            response_model=List[ClientPublic],
            summary="List clients",
            description="Retrieve a paginated list of clients with filtering")
def read_clients(
        response: Response,
        session: SessionDep,
        current_user: CurrentUser,
        filter_: str = Query("{}", alias="filter"),
        range_: str = Query("[0, 500]", alias="range"),
        sort: str = Query('["id", "ASC"]', alias="sort"),
) -> List[ClientPublic]:
    logger.debug(f"User {current_user.username} fetching clients")
    try:
        # Parse query parameters
        filter_dict, range_list, sort_field, sort_order = parse_query_params(
            filter_, range_, sort)

        # Build filters and pagination
        filters = ClientFilters(**filter_dict)
        offset, limit = calculate_pagination(range_list)

        # Build base query
        stmt = select(Client)
        stmt = apply_client_filters(stmt, filters)
        stmt = apply_sorting(stmt, Client, sort_field, sort_order)

        # Get total count
        total = get_total_count(session, stmt)

        # Apply pagination and execute
        stmt = stmt.offset(offset).limit(limit)
        clients = session.exec(stmt).all()

        # Transform to public schema
        result = [transform_client_to_public(client) for client in clients]

        # Set response headers
        set_pagination_headers(response, offset, len(result), total)
        logger.info(f"Retrieved {len(result)}/{total} clients")

        return result
    except HTTPException:
        raise  # Re-raise HTTP exceptions from parse_query_params
    except Exception as e:
        logger.error(f"Error fetching clients: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to retrieve clients")


@router.post("",
             response_model=ClientPublic,
             summary="Create client",
             description="Create a new client in the system")
def create_client(session: SessionDep, current_user: CurrentUser,
                  client_in: ClientCreate) -> ClientPublic:
    logger.debug(
        f"User {current_user.username} creating client: {client_in.phone}")

    stmt = select(Client.id).where(Client.phone == client_in.phone)
    existing_client = session.exec(stmt).one_or_none()
    if existing_client:
        logger.error(f"Client with phone {client_in.phone} already exists")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Client already exists")
    try:
        client = Client(**client_in.model_dump(exclude_unset=True))

        session.add(client)
        session.commit()
        session.refresh(client)

        logger.info(f"Client {client.id} created successfully")
        return transform_client_to_public(client)

    except Exception as e:
        session.rollback()
        logger.error(f"Error creating client: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create client")


@router.get("/{client_id}",
            response_model=ClientPublic,
            summary="Get client",
            description="Retrieve a single client by ID")
def get_client_by_id(session: SessionDep, current_user: CurrentUser,
                     client_id: UUID) -> ClientPublic:

    logger.debug(f"User {current_user.username} fetching client {client_id}")
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Client with ID {client_id} not found")

    logger.info(f"Client {client_id} retrieved successfully")
    return transform_client_to_public(client)


@router.put("/{client_id}",
            response_model=ClientPublic,
            summary="Update client",
            description="Update an existing client by ID")
def update_client(session: SessionDep, current_user: CurrentUser,
                  client_id: UUID, client_in: ClientUpdate) -> ClientPublic:

    logger.debug(f"User {current_user.username} updating client {client_id}")

    # Get existing client
    client = session.get(Client, client_id)
    if not client:
        logger.error(f"Client {client_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Client not found")

    # Validate update data
    update_data = client_in.model_dump(exclude_unset=True)
    if not update_data:
        logger.error(f"No data provided for update")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No data provided for update")
    try:
        # Apply updates
        for field, value in update_data.items():
            setattr(client, field, value)

        client.updated_at = datetime.now(timezone.utc)

        session.add(client)
        session.commit()
        session.refresh(client)

        logger.info(f"Updated client: {id}")
        return transform_client_to_public(client)

    except Exception as e:
        session.rollback()
        logger.error(f"Error updating client {id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to update client")


@router.delete("/{client_id}",
               status_code=status.HTTP_200_OK,
               summary="Delete client",
               description="Delete a client by ID")
def delete_client(session: SessionDep, current_user: CurrentUser,
                  client_id: UUID):
    """Delete a client by ID if it has no active orders."""
    logger.debug(
        f"User {current_user.username} attempting to delete client {client_id}")

    # Fetch client
    client = session.get(Client, client_id)
    if not client:
        logger.warning(f"Client not found for deletion: {client_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Client not found")

    # Check if client has any orders
    stmt = select(func.count()).select_from(Order)
    stmt = stmt.where(Order.client_id == client.id)
    active_orders_count = session.exec(stmt).one()
    if active_orders_count > 0:
        logger.warning(
            f"Client {client.id} has active orders and cannot be deleted")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot delete client: it has active orders")

    try:
        session.delete(client)
        session.commit()

        logger.info(
            f"Client {client.id} deleted successfully by {current_user.username}"
        )
        return {"message": f"Client {client.id} deleted successfully"}

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete client {client_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to delete client")
