# Authentication functionality
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import ValidationError
from fastapi import Request
from fastapi.security import OAuth2PasswordBearer
from argon2 import exceptions as argon2_exceptions
from authlib.integrations.starlette_client import OAuth

# --- Project Imports ---
from core.logger import logger
from core.config import settings
from core.models import User, UserCreate, Token, TokenPayload
from core.database import ph, SessionDep, get_user_by_username, get_user_by_email, create_user
from core.exceptions import AuthenticationException, ConflictException, InternalErrorException

# =====================================================================================
#  Low-Level Auth Primitives
# =====================================================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against an Argon2 hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (argon2_exceptions.VerifyMismatchError,
            argon2_exceptions.VerificationError):
        return False
    except argon2_exceptions.InvalidHash as e:
        logger.warning(f"Invalid password hash encountered: {e}")
        return False


def create_token(data: dict, expires_delta: timedelta, key: str) -> str:
    """Creates a JWT token with a specified expiration."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    payload.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(payload, key, algorithm=settings.ACCESS_TOKEN_ALGORITHM)


def decode_token(token: str, key: str) -> TokenPayload:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token,
                             key,
                             algorithms=[settings.ACCESS_TOKEN_ALGORITHM])
        return TokenPayload(**payload)
    except (jwt.PyJWTError, ValidationError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise AuthenticationException("Could not validate credentials")


def authenticate_user(session, identifier: str,
                      password: str) -> Optional[User]:
    """
    Finds a user by username or email and verifies their password.
    Returns the user object on success, otherwise None.
    """
    if "@" in identifier:
        user = get_user_by_email(session, identifier)
    else:
        user = get_user_by_username(session, identifier)

    if not user or not user.hashed_password:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


# =====================================================================================
#  High-Level Authentication Service
# =====================================================================================
class AuthService:
    """A service class for authentication business logic."""

    def __init__(self):
        self.oauth = OAuth()
        self.oauth.register(
            name="google",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            server_metadata_url=
            "https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"})

    def generate_token_pair(self, username: str) -> Token:
        """Generates a new access and refresh token pair for a user."""
        access_token = create_token(
            data={"sub": username},
            expires_delta=timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS),
            key=settings.ACCESS_TOKEN_SECRET_KEY)
        refresh_token = create_token(
            data={"sub": username},
            expires_delta=timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS),
            key=settings.REFRESH_TOKEN_SECRET_KEY)
        return Token(access_token=access_token,
                     refresh_token=refresh_token,
                     token_type="bearer")

    def validate_user_is_active(self, user: User) -> None:
        """Raises an exception if the user is not active."""
        if not user.is_active:
            logger.warning(f"Inactive user attempted access: {user.username}")
            raise AuthenticationException("Your account is inactive")

    def register_new_user(self, session: SessionDep,
                          user_data: UserCreate) -> User:
        """Registers a new user, checking for existing accounts first."""
        existing_user = get_user_by_username(
            session, user_data.username) or get_user_by_email(
                session, user_data.email)

        if existing_user:
            logger.warning(
                f"Registration failed - user exists: {user_data.username} or {user_data.email}"
            )
            raise ConflictException(
                "A user with this username or email already exists.")
        try:
            new_user = create_user(session, user_data)
            logger.info(f"User registered successfully: {new_user.username}")
            return new_user
        except Exception as e:
            logger.error(f"Registration failed for {user_data.username}: {e}")
            raise InternalErrorException("Failed to create user account.")

    async def handle_google_login(self, request: Request):
        """Initiates the Google OAuth2 authorization flow."""
        redirect_uri = request.url_for("google_callback")
        logger.debug(
            f"Starting Google OAuth flow with redirect: {redirect_uri}")
        return await self.oauth.google.authorize_redirect(request, redirect_uri)

    async def handle_google_callback(self, request: Request,
                                     session: SessionDep) -> User:
        """
        Handles the Google OAuth callback.
        Gets user info, and finds or creates a user.
        """
        try:
            token = await self.oauth.google.authorize_access_token(request)
            user_info = token.get("userinfo")

            if not user_info or not user_info.get("email_verified"):
                raise AuthenticationException(
                    "Could not verify Google account.")

            email = user_info["email"]
            user = get_user_by_email(session, email)
            username = user_info.get("name",
                                     email.split("@")[0].replace(" ", "_"))

            if not user:
                logger.info(f"Creating new external user: {email}")
                user_create = UserCreate(username=username,
                                         email=email,
                                         avatar=user_info.get("picture"),
                                         is_external=True)
                user = create_user(session, user_create)

            return user
        except Exception as e:
            logger.error(f"Google OAuth failed: {e}")
            raise AuthenticationException("OAuth authentication failed")


# --- Service Instance ---
# Create a single, reusable instance of the AuthService
auth_service = AuthService()
