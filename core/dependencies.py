# FastAPI dependencies
from typing import Annotated
from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from core.logger import logger
from core.database import get_session, get_user_by_username
from core.auth import oauth2_scheme, decode_token
from core.models import User

# Type annotations for dependencies
SessionDep = Annotated[Session, Depends(get_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    """Get current authenticated user"""
    token_data = decode_token(token)

    if not token_data.sub:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token: missing subject")

    user = get_user_by_username(session, token_data.sub)
    if not user:
        logger.warning(f"User not found for token subject: {token_data.sub}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="User not found")

    if not user.is_active:
        logger.warning(f"Inactive user tried to authenticate: {user.username}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Account is inactive")

    logger.debug(f"Authenticated user: {user.username}")
    return user


def get_current_superuser(
        current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Ensure current user is a superuser"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Insufficient privileges")
    return current_user


# Type annotation for current user dependency
CurrentUser = Annotated[User, Depends(get_current_user)]
