# Core database functionality
import secrets
from collections.abc import Generator
from time import monotonic
from typing import Annotated

from argon2 import PasswordHasher
from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine, func, select

# --- Project Imports ---
from core.config import settings
from core.exceptions import InternalErrorException
from core.logger import logger
from models.user import User, UserCreate

engine = create_engine(
    settings.database_url,
    echo=False,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
)


@event.listens_for(engine, "checkout")
def _record_checkout(dbapi_connection, connection_record, connection_proxy) -> None:
    connection_record.info["checkout_started_at"] = monotonic()


@event.listens_for(engine, "checkin")
def _log_long_checkout(dbapi_connection, connection_record) -> None:
    started_at = connection_record.info.pop("checkout_started_at", None)
    if started_at is None:
        return
    held_seconds = monotonic() - started_at
    if held_seconds >= settings.DB_LONG_CHECKOUT_SECONDS:
        logger.warning(
            "Database connection held for %.2f seconds; %s",
            held_seconds,
            engine.pool.status(),
        )


ph = PasswordHasher()


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


# --- Session Management ---
def get_session() -> Generator[Session]:
    """Dependency to get a new database session for each request"""
    with Session(engine) as session:
        yield session


type SessionDep = Annotated[Session, Depends(get_session)]


def hash_password(password: str) -> str:
    return ph.hash(password)


# User database operations
def get_user_by_username(session: Session, username: str) -> User | None:
    """Retrieves a user from the database by their username"""
    stmt = select(User).where(User.username == username)
    return session.exec(stmt).first()


def get_user_by_email(session: Session, email: str) -> User | None:
    """Retrieves a user from the database by their email address"""
    stmt = select(User).where(User.email == email)
    return session.exec(stmt).first()


def create_user(session: Session, user_in: UserCreate) -> User:
    """Creates a new user in the database"""
    logger.debug(f"Creating user {user_in.username}")

    password_to_hash = user_in.password or secrets.token_urlsafe(16)
    hashed_password = hash_password(password_to_hash)

    user_data = user_in.model_dump(exclude={"password"})
    db_user = User(**user_data, hashed_password=hashed_password)

    try:
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        logger.info(f"User {db_user.username} created successfully (id={db_user.id})")
        return db_user
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error creating user '{user_in.username}': {e}")
        raise InternalErrorException(
            "An unexpected error occurred while creating the user."
        )


def get_total_count(session: Session, stmt) -> int:
    """Executes a count query to get the total number of records"""
    count_stmt = select(func.count()).select_from(stmt.subquery())
    return session.exec(count_stmt).one()
