from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import func, select

from core.database import SessionDep
from core.exceptions import BadRequestException, ConflictException

# --- Project Imports ---
from core.logger import logger
from core.query_gateway import QueryGateway
from models.client import Client, ClientCreate, ClientFilters, ClientUpdate
from models.order import Order
from services.client_query_gateway import ClientQueryGateway


class ClientService:
    """Business logic for client operations"""

    def __init__(self, session: SessionDep):
        self.session = session
        self.query_gateway: QueryGateway[Client, ClientFilters] = ClientQueryGateway(
            session
        )

    def get_by_id(self, client_id: UUID) -> Client:
        """Get client by ID"""
        logger.debug(f"Fetching client by ID: {client_id}")
        return self.query_gateway.get_by_id(client_id)

    def get_clients(
        self,
        filters: ClientFilters,
        offset: int = 0,
        limit: int = 100,
        sort_field: str = "id",
        sort_order: str = "ASC",
    ) -> tuple[list[Client], int]:
        """Get filtered and paginated clients with total count"""
        return self.query_gateway.list(
            filters=filters,
            offset=offset,
            limit=limit,
            sort_field=sort_field,
            sort_order=sort_order,
        )

    def create(self, client_in: ClientCreate) -> Client:
        """Create a new client"""
        logger.debug(f"Creating client with phone: {client_in.phone}")

        # Check for duplicate phone
        stmt = select(Client.id).where(Client.phone == client_in.phone)
        existing = self.session.exec(stmt).one_or_none()
        if existing:
            logger.warning(f"Client with phone {client_in.phone} already exists")
            raise ConflictException("Client with such phone already exists")

        client = Client(**client_in.model_dump(exclude_unset=True))
        self.session.add(client)
        self.session.commit()
        self.session.refresh(client)

        logger.info(f"Client created successfully: {client.id}")
        return client

    def update(self, client: Client, client_in: ClientUpdate) -> Client:
        """Update existing client"""
        logger.debug(f"Updating client: {client.id}")

        update_data = client_in.model_dump(exclude_unset=True)
        if not update_data:
            logger.warning("No data provided for update")
            raise BadRequestException("No data provided for update")

        # Check if phone is being updated and if it already exists
        if "phone" in update_data and update_data["phone"] != client.phone:
            stmt = select(Client.id)
            stmt = stmt.where(Client.phone == update_data["phone"])
            stmt = stmt.where(Client.id != client.id)
            existing = self.session.exec(stmt).first()
            if existing:
                logger.warning(
                    f"Phone {update_data['phone']} already exists for another client"
                )
                raise ConflictException(
                    f"Phone number {update_data['phone']} is already in use"
                )

        for field, value in update_data.items():
            setattr(client, field, value)

        client.updated_at = datetime.now(UTC)
        self.session.add(client)
        self.session.commit()
        self.session.refresh(client)

        logger.info(f"Client updated successfully: {client.id}")
        return client

    def delete(self, client: Client) -> None:
        """Delete client if no active orders exist"""
        logger.debug(f"Attempting to delete client: {client.id}")

        if self.has_orders(client.id):
            logger.warning(f"Cannot delete client {client.id}: has orders")
            raise BadRequestException("Cannot delete client: has active orders")

        self.session.delete(client)
        self.session.commit()
        logger.info(f"Client deleted successfully: {client.id}")

    def has_orders(self, client_id: UUID) -> bool:
        stmt = select(func.count()).select_from(Order)
        stmt = stmt.where(Order.client_id == client_id)
        count = self.session.exec(stmt).one()
        return count > 0
