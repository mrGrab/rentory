# Authentication functionality
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import ValidationError
from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException, status
from argon2 import exceptions as argon2_exceptions

from core.config import settings
from core.logger import logger
from core.models import User, TokenPayload
from core.database import ph, get_user_by_username, get_user_by_email

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    try:
        return ph.verify(hashed_password, plain_password)
    except (argon2_exceptions.VerifyMismatchError,
            argon2_exceptions.VerificationError,
            argon2_exceptions.InvalidHash) as e:
        logger.warning(f"Password verification failed: {e}")
        return False


def authenticate_user(session,
                      password: str,
                      username: Optional[str] = None,
                      email: Optional[str] = None) -> Optional[User]:
    """Authenticate user by username or email"""
    if username:
        user = get_user_by_username(session, username)
    elif email:
        user = get_user_by_email(session, email)
    else:
        return None

    if not user or not user.hashed_password:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


def decode_token(token: str,
                 key=settings.ACCESS_TOKEN_SECRET_KEY) -> TokenPayload:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(jwt=token,
                             key=key,
                             algorithms=[settings.ACCESS_TOKEN_ALGORITHM])
        return TokenPayload(**payload)
    except (jwt.InvalidTokenError, ValidationError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Could not validate credentials")


def create_token(data: dict,
                 expires_delta: Optional[timedelta] = None,
                 key=settings.ACCESS_TOKEN_SECRET_KEY):
    """Create JWT token"""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=2))
    payload.update({"exp": expire})
    return jwt.encode(payload=payload,
                      key=key,
                      algorithm=settings.ACCESS_TOKEN_ALGORITHM)
