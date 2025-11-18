# FastAPI dependencies

# --- Core Imports ---
from typing import Annotated
from fastapi import Depends

# --- Project Imports ---
from core.logger import logger
from core.config import settings
from core.database import SessionDep, get_user_by_username
from core.auth import oauth2_scheme, decode_token
from models.user import User
from core.exceptions import AuthenticationException, PermissionException

TokenDep = Annotated[str, Depends(oauth2_scheme)]


# ================================================================================
#  Authentication & Authorization Dependencies
# ================================================================================
def get_current_user(session: SessionDep, token: TokenDep) -> User:
    """
    Dependency to decode a JWT token, validate its subject, and return the
    corresponding active user from the database.
    """
    token_data = decode_token(token, settings.ACCESS_TOKEN_SECRET_KEY)

    username = token_data.sub
    if not username:
        raise AuthenticationException("Invalid token: subject missing")

    user = get_user_by_username(session, username)
    if not user:
        logger.warning(
            f"Authentication failed: user '{username}' from token not found.")
        raise AuthenticationException(
            "User associated with this token no longer exists")

    if not user.is_active:
        logger.warning(f"Permission denied: user '{username}' is inactive.")
        raise PermissionException("Your account is inactive")

    logger.debug(f"Authenticated user: {user.username}")
    return user


def get_current_superuser(
        current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """
    Dependency that requires the current user to be a superuser.
    Builds upon `get_current_user`.
    """
    if not current_user.is_superuser:
        logger.warning(
            f"Permission denied: user '{current_user.username}' lacks superuser privileges."
        )
        raise PermissionException("This action requires superuser privileges")
    return current_user


# ================================================================================
#  Combined Dependency Annotations for API Routes
# ================================================================================
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
