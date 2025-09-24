from datetime import timedelta
from typing import Annotated
from fastapi import Depends, APIRouter, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from authlib.integrations.starlette_client import OAuth

# --- Project Imports ---
from core.config import settings
from core.logger import logger
from core.models import Token, UserCreate, User
from core.dependencies import CurrentUser
from core.database import SessionDep, get_user_by_username
from core.auth import auth_service, authenticate_user, decode_token
from core.exceptions import AuthenticationException

router = APIRouter(tags=["Authentication"])


@router.post("/login",
             response_model=Token,
             summary="User login",
             description="Authenticate user with username/email and password")
def login(session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm,
                                                    Depends()]) -> Token:
    """
    Authenticates a user with username/email and password.
    Returning a token pair.
    """
    logger.debug(f"Login attempt for: {form_data.username}")

    user = authenticate_user(session,
                             identifier=form_data.username,
                             password=form_data.password)
    if not user:
        raise AuthenticationException("Incorrect username or password")

    auth_service.validate_user_is_active(user)
    logger.info(f"User logged in successfully: {user.username}")
    return auth_service.generate_token_pair(user.username)


@router.post("/register",
             response_model=Token,
             status_code=201,
             summary="User Registration")
def register_user(session: SessionDep, user_data: UserCreate) -> Token:
    """Creates a new user account and returns a token pair."""
    new_user = auth_service.register_new_user(session, user_data)
    return auth_service.generate_token_pair(new_user.username)


@router.post("/refresh",
             response_model=Token,
             summary="Refresh Access Token",
             description="Exchange refresh token for new access token")
def refresh_access_token(session: SessionDep, refresh_token: str) -> Token:
    """Exchanges a valid refresh token for a new token pair."""
    try:
        token_data = decode_token(token=refresh_token,
                                  key=settings.REFRESH_TOKEN_SECRET_KEY)
        user = get_user_by_username(session, token_data.sub)
        if not user:
            raise AuthenticationException("User from token not found")

        auth_service.validate_user_is_active(user)
        logger.info(f"Token refreshed for user: {user.username}")
        return auth_service.generate_token_pair(user.username)
    except Exception as e:
        logger.warning(f"Invalid refresh token received: {e}")
        raise AuthenticationException("Invalid or expired refresh token")


@router.get("/google/login",
            summary="Google OAuth login",
            description="Initiate Google OAuth authentication flow")
async def google_login(request: Request):
    """Redirects the user to Google's authentication page."""
    return await auth_service.handle_google_login(request)


@router.get("/google/callback", summary="Handle Google OAuth Callback")
async def google_callback(request: Request, session: SessionDep):
    """
    Handles the callback from Google.
    Authenticates the user, and redirects to the frontend with tokens.
    """
    user = await auth_service.handle_google_callback(request, session)
    auth_service.validate_user_is_active(user)
    token_pair = auth_service.generate_token_pair(user.username)

    redirect_url = (f"{settings.FRONTEND_CALLBACK_URL}?"
                    f"access_token={token_pair.access_token}&"
                    f"refresh_token={token_pair.refresh_token}")
    return RedirectResponse(url=redirect_url)


@router.post("/logout", summary="User Logout")
async def logout(request: Request):
    """Provides a conventional endpoint for logging out."""
    if hasattr(request, 'session') and request.session:
        request.session.clear()
        logger.info("User session cleared")
    return {"message": "Successfully logged out. Please discard your tokens."}


@router.get("/verify-token", summary="Verify Access Token")
async def verify_token(current_user: CurrentUser):
    """
    Validates the current user's access token and returns user details.
    """
    logger.debug(f"Token verified for user: {current_user.username}")
    return {
        "is_valid": True,
        "user": {
            "id": str(current_user.id),
            "username": current_user.username,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
        },
    }
