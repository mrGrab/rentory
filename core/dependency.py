import jwt
import json
from typing import Annotated, Generator, List
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from argon2 import PasswordHasher, exceptions as argon2_exceptions
from sqlmodel import Session, SQLModel, create_engine, select, func
from core.logger import logger
from core.config import settings
from core.models import User, TokenPayload

# ---------------------
# Password hasher
# ---------------------
ph = PasswordHasher()

# ---------------------
# OAuth2 token scheme
# ---------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login/access-token")
TokenDep = Annotated[str, Depends(oauth2_scheme)]

# ---------------------
# Database utilities
# ---------------------
DATABASE_FILE = "database.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"
engine = create_engine(DATABASE_URL,
                       connect_args={"check_same_thread": False},
                       echo=False)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


SessionDep = Annotated[Session, Depends(get_session)]


# ---------------------
# Utility functions
# ---------------------
def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except (argon2_exceptions.VerifyMismatchError,
            argon2_exceptions.VerificationError,
            argon2_exceptions.InvalidHash) as e:
        logger.warning(f"Password verification failed: {e}")
        return False


def get_user_by_username(session: SessionDep, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return session.exec(stmt).first()


def get_user_by_email(session: SessionDep, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return session.exec(stmt).first()


def authenticate_user(session: SessionDep, username: str,
                      password: str) -> User | None:
    user = get_user_by_username(session, username)
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(token,
                             settings.ACCESS_TOKEN_SECRET_KEY,
                             algorithms=[settings.ACCESS_TOKEN_ALGORITHM])
        token_data = TokenPayload(**payload)
        if token_data.sub is None:
            raise ValueError("Token 'sub' claim is missing")
    except (jwt.InvalidTokenError, ValidationError, ValueError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Could not validate credentials")
    user = get_user_by_username(session, token_data.sub)
    if not user:
        logger.warning(f"User not found for token subject: {token_data.sub}")
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        logger.warning(f"Inactive user tried to authenticate: {user.username}")
        raise HTTPException(status_code=400, detail="Inactive user")
    logger.debug(f"Authenticated user: {user.username}")
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode,
                             settings.ACCESS_TOKEN_SECRET_KEY,
                             algorithm=settings.ACCESS_TOKEN_ALGORITHM)
    return encoded_jwt


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403,
                            detail="The user doesn't have enough privileges")
    return current_user


def save_to_db(session: SessionDep, obj: SQLModel) -> SQLModel | None:
    try:
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj
    except Exception as e:
        logger.error(f"Failed to save entity: {e}")
        session.rollback()
        return None


# Helper functions for better separation of concerns
def parse_query_params(filter_: str, range_: str, sort: str) -> tuple:
    """Parse and validate query parameters."""
    try:
        filters = json.loads(filter_)
        range_list = json.loads(range_)
        sort_field, sort_order = json.loads(sort)
        return filters, range_list, sort_field, sort_order.upper()
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400,
                            detail=f"Invalid query parameters: {e}")


def calculate_pagination(range_list: List[int]) -> tuple:
    """Calculate offset and limit from range."""
    offset = range_list[0]
    limit = range_list[1] - range_list[0] + 1
    return offset, limit


def apply_sorting(stmt, model: object, sort_field: str, sort_order: str):
    """Apply sorting to the query statement."""
    try:
        sort_column = getattr(model, sort_field)
        if sort_order.upper() == "ASC":
            return stmt.order_by(sort_column.asc())
        else:
            return stmt.order_by(sort_column.desc())
    except AttributeError:
        logger.warning(f"Invalid sort field: {sort_field}, using default")
        return stmt.order_by(model.created_at.desc())


def get_total_count(session, stmt) -> int:
    """Get total count of records matching the query."""
    stmt_count = select(func.count()).select_from(stmt.subquery())
    return session.exec(stmt_count).one()


def set_pagination_headers(response: Response, offset: int, count: int,
                           total: int):
    """Set pagination headers for the response."""
    end_index = offset + count - 1 if count > 0 else offset
    content_range = f"orders {offset}-{end_index}/{total}"

    response.headers.update({
        "Content-Range": content_range,
        "X-Total-Count": str(total),
        "Access-Control-Expose-Headers": "Content-Range, X-Total-Count",
        "Content-Type": "application/json"
    })
