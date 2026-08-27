from sqlalchemy.sql.expression import Select

from core.sqlmodel_query_gateway import SQLModelQueryGateway
from models.client import Client, ClientFilters


def apply_client_filters(stmt: Select, filters: ClientFilters) -> Select:
    """Filter strategy for client queries used by the query gateway module."""
    if filters.id:
        stmt = stmt.where(Client.id.in_(filters.id))
    if filters.phone:
        stmt = stmt.where(Client.phone.ilike(f"%{filters.phone}%"))
    if filters.email:
        stmt = stmt.where(Client.email.ilike(f"%{filters.email}%"))
    if filters.instagram:
        stmt = stmt.where(Client.instagram.ilike(f"%{filters.instagram}%"))
    if filters.given_name:
        stmt = stmt.where(Client.given_name.ilike(f"%{filters.given_name}%"))
    if filters.surname:
        stmt = stmt.where(Client.surname.ilike(f"%{filters.surname}%"))
    if filters.discount is not None:
        stmt = stmt.where(Client.discount == filters.discount)
    if filters.is_archived is not None:
        stmt = stmt.where(Client.is_archived == filters.is_archived)
    if filters.is_trusted is not None:
        stmt = stmt.where(Client.is_trusted == filters.is_trusted)

    return stmt.distinct()


class ClientQueryGateway(SQLModelQueryGateway[Client, ClientFilters]):
    def __init__(self, session):
        super().__init__(
            session=session, model=Client, apply_filters=apply_client_filters
        )
