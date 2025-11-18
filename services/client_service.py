from uuid import UUID
from typing import List
from sqlmodel import select, func
from datetime import datetime, timezone

# --- Project Imports ---
from core.query_utils import apply_sorting
from core.logger import logger
from core.database import SessionDep
from core.database import get_total_count
from core.exceptions import ConflictException, BadRequestException
from models.order import Order
from models.client import Client, ClientCreate, ClientUpdate, ClientFilters


class ClientService:
    """Business logic for client operations"""

    def __init__(self, session: SessionDep):
        self.session = session

    def _apply_filters(self, stmt, filters: ClientFilters):
        """Apply filters to client query"""
        if filters.id:
            stmt = stmt.where(Client.id.in_(filters.id))
        if filters.phone:
            stmt = stmt.where(Client.phone.ilike(f"%{filters.phone}%"))
        if filters.email:
            stmt = stmt.where(Client.email.ilike(f"%{filters.email}%"))
        if filters.instagram:
            stmt = stmt.where(Client.instagram.ilike(f"%{filters.instagram}%"))
        if filters.given_name:
            stmt = stmt.where(
                Client.given_name.ilike(f"%{filters.given_name}%"))
        if filters.surname:
            stmt = stmt.where(Client.surname.ilike(f"%{filters.surname}%"))
        if filters.discount is not None:
            stmt = stmt.where(Client.discount == filters.discount)
        if filters.is_archived is not None:
            stmt = stmt.where(Client.is_archived == filters.is_archived)

        return stmt.distinct()

    def get_by_id(self, client_id: UUID) -> Client:
        """Get client by ID"""
        logger.debug(f"Fetching client by ID: {client_id}")
        return self.session.get(Client, client_id)

    def get_clients(self,
                    filters: ClientFilters,
                    offset: int = 0,
                    limit: int = 100,
                    sort_field: str = "id",
                    sort_order: str = "ASC") -> tuple[List[Client], int]:
        """Get filtered and paginated clients with total count"""
        stmt = select(Client)
        stmt = self._apply_filters(stmt, filters)
        stmt = apply_sorting(stmt, Client, sort_field, sort_order)

        # Get total count before pagination
        total = get_total_count(self.session, stmt)

        stmt = stmt.offset(offset).limit(limit)
        clients = self.session.exec(stmt).all()

        return clients, total

    def create(self, client_in: ClientCreate) -> Client:
        """Create a new client"""
        logger.debug(f"Creating client with phone: {client_in.phone}")

        # Check for duplicate phone
        stmt = select(Client.id).where(Client.phone == client_in.phone)
        existing = self.session.exec(stmt).one_or_none()
        if existing:
            logger.warning(
                f"Client with phone {client_in.phone} already exists")
            raise ConflictException(f"Client with such phone already exists")

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
                    f"Phone number {update_data['phone']} is already in use")

        for field, value in update_data.items():
            setattr(client, field, value)

        client.updated_at = datetime.now(timezone.utc)
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
            raise BadRequestException(
                "Cannot delete client: has active orders")

        self.session.delete(client)
        self.session.commit()
        logger.info(f"Client deleted successfully: {client.id}")

    def has_orders(self, client_id: UUID) -> bool:
        stmt = select(func.count()).select_from(Order)
        stmt = stmt.where(Order.client_id == client_id)
        count = self.session.exec(stmt).one()
        return count > 0
