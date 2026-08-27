from sqlalchemy.sql.expression import Select

from core.sqlmodel_query_gateway import SQLModelQueryGateway
from models.user import User, UserFilters


def apply_user_filters(stmt: Select, filters: UserFilters) -> Select:
    """Filter strategy for user queries used by the query gateway module."""
    if filters.id:
        if isinstance(filters.id, list):
            stmt = stmt.where(User.id.in_(filters.id))
        else:
            stmt = stmt.where(User.id.contains(filters.id))

    if filters.is_external is not None:
        stmt = stmt.where(User.is_external == filters.is_external)

    if filters.is_active is not None:
        stmt = stmt.where(User.is_active == filters.is_active)

    if filters.is_superuser is not None:
        stmt = stmt.where(User.is_superuser == filters.is_superuser)

    return stmt.distinct()


class UserQueryGateway(SQLModelQueryGateway[User, UserFilters]):
    def __init__(self, session):
        super().__init__(session=session, model=User, apply_filters=apply_user_filters)
