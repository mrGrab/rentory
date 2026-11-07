from sqlalchemy.sql.expression import Select
from sqlmodel import Session, col

from core.sqlmodel_query_gateway import SQLModelQueryGateway
from models.client import Client, ClientFilters


def apply_client_filters(
    stmt: Select[tuple[Client]], filters: ClientFilters
) -> Select[tuple[Client]]:
    """Filter strategy for client queries used by the query gateway module."""
    if filters.id:
        stmt = stmt.where(col(Client.id).in_(filters.id))
    if filters.phone:
        stmt = stmt.where(col(Client.phone).ilike(f"%{filters.phone}%"))
    if filters.email:
        stmt = stmt.where(col(Client.email).ilike(f"%{filters.email}%"))
    if filters.instagram:
        stmt = stmt.where(col(Client.instagram).ilike(f"%{filters.instagram}%"))
    if filters.given_name:
        stmt = stmt.where(col(Client.given_name).ilike(f"%{filters.given_name}%"))
    if filters.surname:
        stmt = stmt.where(col(Client.surname).ilike(f"%{filters.surname}%"))
    if filters.discount is not None:
        stmt = stmt.where(col(Client.discount) == filters.discount)
    if filters.is_archived is not None:
        stmt = stmt.where(col(Client.is_archived) == filters.is_archived)
    if filters.is_trusted is not None:
        stmt = stmt.where(col(Client.is_trusted) == filters.is_trusted)

    return stmt.distinct()


class ClientQueryGateway(SQLModelQueryGateway[Client, ClientFilters]):
    def __init__(self, session: Session):
        super().__init__(
            session=session, model=Client, apply_filters=apply_client_filters
        )
