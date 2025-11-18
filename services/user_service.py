from uuid import UUID
from typing import List, Optional
from sqlmodel import select

# --- Project Imports ---
from core.query_utils import apply_sorting
from core.logger import logger
from core.exceptions import ConflictException
from models.user import User, UserCreate, UserFilters
from core.database import SessionDep, get_total_count, create_user, get_user_by_username, get_user_by_email


class UserService:
    """Business logic for user operations"""

    def __init__(self, session: SessionDep):
        self.session = session

    def _apply_filters(self, stmt, filters: UserFilters):
        """Apply user filters to the query statement"""
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

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get a specific user by ID"""
        logger.debug(f"Fetching user by ID: {user_id}")
        return self.session.get(User, user_id)

    def get_users(self,
                  filters: UserFilters,
                  offset: int = 0,
                  limit: int = 100,
                  sort_field: str = "id",
                  sort_order: str = "ASC") -> tuple[List[User], int]:
        """Get filtered and paginated users with total count"""
        logger.debug("Fetching users")

        stmt = select(User)
        stmt = self._apply_filters(stmt, filters)
        stmt = apply_sorting(stmt, User, sort_field, sort_order)

        # Get total count before pagination
        total = get_total_count(self.session, stmt)

        stmt = stmt.offset(offset).limit(limit)
        users = self.session.exec(stmt).all()

        return users, total

    def create(self, user_in: UserCreate) -> User:
        """Create a new user"""
        logger.debug(f"Creating user with username: {user_in.username}")

        # Check if user already exists
        if get_user_by_username(self.session, user_in.username):
            logger.warning(f"Username already exists: {user_in.username}")
            raise ConflictException(
                f"Username '{user_in.username}' already exists")

        if get_user_by_email(self.session, user_in.email):
            logger.warning(f"Email already exists: {user_in.email}")
            raise ConflictException(f"Email '{user_in.email}' already exists")

        user = create_user(self.session, user_in)
        logger.info(f"Successfully created user: {user.username}")
        return user
