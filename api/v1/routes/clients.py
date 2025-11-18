from uuid import UUID
from typing import List
from fastapi import APIRouter, HTTPException, Query, status, Response, Depends

# --- Project Imports ---
from core.query_utils import parse_params, calculate_pagination, set_pagination_headers
from core.logger import logger
from core.dependencies import CurrentUser
from core.database import SessionDep
from core.exceptions import InternalErrorException, NotFoundException
from services.client_service import ClientService
from models.client import Client, ClientCreate, ClientUpdate, ClientPublic, ClientFilters

router = APIRouter(prefix="/clients", tags=["Clients"])

# ---------- Helper Functions ----------


def get_client_service(session: SessionDep) -> ClientService:
    """Dependency to get ClientService instance"""
    return ClientService(session)


def get_client_or_404(
    client_id: UUID, service: ClientService = Depends(get_client_service)
) -> Client:
    """Dependency to retrieve a client by ID or raise NotFoundException"""
    client = service.get_by_id(client_id)
    if not client:
        logger.warning(f"Client not found: {client_id}")
        raise NotFoundException(f"Client with ID {client_id} not found")
    return client


def to_public(client: Client) -> ClientPublic:
    """Convert Client to ClientPublic with order IDs"""
    order_ids = [order.id for order in client.orders] if client.orders else []
    return ClientPublic(**client.model_dump(), order_ids=order_ids)


# ---------- Routes ----------


@router.get("",
            response_model=List[ClientPublic],
            summary="List clients",
            description="Retrieve a paginated list of clients with filtering")
def list_clients(response: Response,
                 current_user: CurrentUser,
                 service: ClientService = Depends(get_client_service),
                 filter_: str = Query("{}", alias="filter"),
                 range_: str = Query("[0, 500]", alias="range"),
                 sort: str = Query('["id", "ASC"]', alias="sort")):

    logger.debug(f"User {current_user.username} listing clients")

    params = parse_params(filter_, range_, sort)
    filters = ClientFilters(**params.filters)
    offset, limit = calculate_pagination(params.range_list)

    clients, total = service.get_clients(filters=filters,
                                         offset=offset,
                                         limit=limit,
                                         sort_field=params.sort_field,
                                         sort_order=params.sort_order)

    result = [to_public(client) for client in clients]

    set_pagination_headers(response=response,
                           count=len(result),
                           total=total,
                           offset=offset,
                           resource_name="clients")
    logger.info(
        f"User {current_user.username} retrieved {len(result)}/{total} clients"
    )

    return result


@router.post("",
             response_model=ClientPublic,
             status_code=status.HTTP_201_CREATED,
             summary="Create client",
             description="Create a new client in the system")
def create_client(client_in: ClientCreate,
                  current_user: CurrentUser,
                  service: ClientService = Depends(get_client_service)):
    logger.debug(f"User {current_user.username} creating client")

    client = service.create(client_in)

    logger.info(f"User {current_user.username} created client {client.id}")
    return to_public(client)


@router.get("/{client_id}",
            response_model=ClientPublic,
            summary="Get client by ID",
            description="Retrieve a single client by their UUID")
def read_client(current_user: CurrentUser,
                client: Client = Depends(get_client_or_404)):
    """Retrieve a specific client by ID."""
    logger.info(f"User {current_user.username} retrieved client {client.id}")
    return to_public(client)


@router.put("/{client_id}",
            response_model=ClientPublic,
            summary="Update client",
            description="Update an existing client's information")
def update_client(current_user: CurrentUser,
                  client_in: ClientUpdate,
                  client: Client = Depends(get_client_or_404),
                  service: ClientService = Depends(get_client_service)):
    logger.info(f"User {current_user.username} updating client {client.id}")

    updated_client = service.update(client, client_in)
    logger.info(f"User {current_user.username} updated client {client.id}")
    return to_public(updated_client)


@router.delete("/{client_id}",
               status_code=status.HTTP_200_OK,
               summary="Delete client",
               description="Delete a client if they have no active orders")
def delete_client(current_user: CurrentUser,
                  client: Client = Depends(get_client_or_404),
                  service: ClientService = Depends(get_client_service)):

    logger.info(f"User {current_user.username} deleting client {client.id}")

    service.delete(client)
    logger.info(f"User {current_user.username} deleted client {client.id}")
    return {"message": f"Client {client.id} deleted successfully"}
