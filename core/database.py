# Core database functionality
import secrets
from typing import Generator, Annotated
from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine, select, func
from argon2 import PasswordHasher

# --- Project Imports ---
from core.config import settings
from core.logger import logger
from models.user import User, UserCreate
from core.exceptions import InternalErrorException

engine = create_engine(settings.database_url, echo=False)
ph = PasswordHasher()


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


# --- Session Management ---
def get_session() -> Generator[Session, None, None]:
    """Dependency to get a new database session for each request"""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


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
        logger.info(
            f"User {db_user.username} created successfully (id={db_user.id})")
        return db_user
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating user '{user_in.username}': {e}")
        raise InternalErrorException(
            "An unexpected error occurred while creating the user.")


def get_total_count(session: Session, stmt) -> int:
    """Executes a count query to get the total number of records"""
    count_stmt = select(func.count()).select_from(stmt.subquery())
    return session.exec(count_stmt).one()
