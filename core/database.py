# Core database functionality
import json
import secrets
from pathlib import Path
from typing import Generator, List
from fastapi import HTTPException, Response, status
from sqlmodel import Session, SQLModel, create_engine, select, func
from argon2 import PasswordHasher

from core.config import settings
from core.logger import logger
from core.models import User, UserCreate

engine = create_engine(settings.database_url, echo=False)
ph = PasswordHasher()


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def hash_password(password: str) -> str:
    return ph.hash(password)


# User database operations
def get_user_by_username(session: Session, username: str) -> User | None:
    """Find user by username"""
    stmt = select(User).where(User.username == username)
    return session.exec(stmt).first()


def get_user_by_email(session: Session, email: str) -> User | None:
    """Find user by email"""
    stmt = select(User).where(User.email == email)
    return session.exec(stmt).first()


def create_user(session: Session, user_in: UserCreate) -> User:
    """Create a new user"""
    logger.debug(f"Creating user {user_in.username}")

    if not user_in.password:
        user_in.password = secrets.token_urlsafe(12)
    hashed_password = hash_password(user_in.password)

    try:
        user = User(**user_in.model_dump(exclude_unset=True,
                                         exclude={"password"}),
                    hashed_password=hashed_password)
        session.add(user)
        session.commit()
        session.refresh(user)
        logger.info(f"User created successfully (id={user.id})")
        return user
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating user {user_in.username}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create user")


# Query utilities
def parse_query_params(filter_: str, range_: str, sort: str) -> tuple:
    """Parse and validate query parameters"""
    try:
        filters = json.loads(filter_)
        range_list = json.loads(range_)
        sort_field, sort_order = json.loads(sort)
        return filters, range_list, sort_field, sort_order.upper()
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid query parameters: {e}")


def calculate_pagination(range_list: List[int]) -> tuple:
    """Calculate offset and limit from range"""
    offset = range_list[0]
    limit = range_list[1] - range_list[0] + 1
    return offset, limit


def apply_sorting(stmt, model: object, sort_field: str, sort_order: str):
    """Apply sorting to query"""
    try:
        sort_column = getattr(model, sort_field)
        if sort_order == "ASC":
            return stmt.order_by(sort_column.asc())
        else:
            return stmt.order_by(sort_column.desc())
    except AttributeError:
        logger.warning(f"Invalid sort field: {sort_field}, using default")
        return stmt.order_by(model.created_at.desc())


def get_total_count(session: Session, stmt) -> int:
    """Get total count of records"""
    stmt_count = select(func.count()).select_from(stmt.subquery())
    return session.exec(stmt_count).one()


def set_pagination_headers(response: Response, offset: int, count: int,
                           total: int):
    """Set pagination headers"""
    end_index = offset + count - 1 if count > 0 else offset
    content_range = f"orders {offset}-{end_index}/{total}"
    response.headers.update({
        "Content-Range": content_range,
        "X-Total-Count": str(total),
        "Access-Control-Expose-Headers": "Content-Range, X-Total-Count",
        "Content-Type": "application/json"
    })
