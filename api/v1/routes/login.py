from datetime import timedelta
from typing import Annotated

from fastapi import Depends, APIRouter, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from authlib.integrations.starlette_client import OAuth

from core.config import settings
from core.logger import logger
from core.models import Token, UserCreate, User
from core.dependencies import SessionDep, CurrentUser
from core.database import create_user, get_user_by_username, get_user_by_email
from core.auth import authenticate_user, create_token, decode_token

router = APIRouter(tags=["Authentication"])

# OAuth configuration
oauth = OAuth()
oauth.register(name="google",
               client_id=settings.GOOGLE_CLIENT_ID,
               client_secret=settings.GOOGLE_CLIENT_SECRET,
               server_metadata_url=
               "https://accounts.google.com/.well-known/openid-configuration",
               client_kwargs={"scope": "openid email profile"})


class AuthenticationError(HTTPException):
    """Custom authentication error with consistent format"""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED,
                         detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})


def generate_token_pair(username: str) -> Token:
    """Generate access and refresh token pair for user"""
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


def find_user_by_identifier(session: SessionDep,
                            identifier: str) -> User | None:
    """Find user by username or email based on identifier format"""
    if "@" in identifier:
        return get_user_by_email(session, identifier)
    else:
        return get_user_by_username(session, identifier)


def validate_user_active(user: User) -> None:
    """Validate that user account is active"""
    if not user.is_active:
        logger.warning(f"Inactive user attempted access: {user.username}")
        raise AuthenticationError("Account is inactive")


@router.post("/login",
             response_model=Token,
             summary="User login",
             description="Authenticate user with username/email and password")
def login(session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm,
                                                    Depends()]) -> Token:
    """Login with username/email and password"""
    logger.debug(f"Login attempt for: {form_data.username}")

    # Determine if identifier is email or username
    if "@" in form_data.username:
        user = authenticate_user(session,
                                 form_data.password,
                                 email=form_data.username)
    else:
        user = authenticate_user(session,
                                 form_data.password,
                                 username=form_data.username)
    if not user:
        logger.warning(
            f"Login failed - invalid credentials: {form_data.username}")
        raise AuthenticationError("Incorrect username or password")

    validate_user_active(user)

    logger.info(f"User logged in successfully: {user.username}")
    return generate_token_pair(user.username)


@router.post("/refresh",
             response_model=Token,
             summary="Refresh access token",
             description="Exchange refresh token for new access token")
def refresh_access_token(session: SessionDep, refresh_token: str) -> Token:
    """Refresh access token using refresh token"""
    try:
        token_data = decode_token(token=refresh_token,
                                  key=settings.REFRESH_TOKEN_SECRET_KEY)
    except HTTPException as e:
        logger.warning(f"Invalid refresh token: {e.detail}")
        raise AuthenticationError("Invalid refresh token")

    user = get_user_by_username(session, token_data.sub)
    if not user:
        logger.warning(f"User not found for refresh token: {token_data.sub}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="User not found")

    validate_user_active(user)

    logger.info(f"Access token refreshed for user: {user.username}")
    return generate_token_pair(user.username)


# @router.post("/register",
#              response_model=Token,
#              status_code=status.HTTP_201_CREATED,
#              summary="Register new user",
#              description="Create new user account and return JWT tokens")
# def register_user(session: SessionDep, user_data: UserCreate) -> Token:
#     """Register a new user account"""
#     logger.info(f"Registration attempt for user: {user_data.username}")
#
#     # Check if user already exists
#     existing_user = (get_user_by_username(session, user_data.username) or
#                      get_user_by_email(session, user_data.email))
#
#     if existing_user:
#         logger.warning(f"Registration failed - user exists: {user_data.username}")
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="User with this username or email already exists"
#         )
#
#     try:
#         user = create_user(session, user_data)
#         logger.info(f"User registered successfully: {user.username}")
#         return generate_token_pair(user.username)
#     except Exception as e:
#         logger.error(f"Registration failed for {user_data.username}: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to create user account"
#         )


@router.get("/google/login",
            summary="Google OAuth login",
            description="Initiate Google OAuth authentication flow")
async def google_login(request: Request):
    """Start Google OAuth flow"""
    redirect_uri = request.url_for('google_callback')
    logger.debug(f"Starting Google OAuth flow with redirect: {redirect_uri}")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback",
            summary="Google OAuth callback",
            description="Handle Google OAuth callback and return JWT tokens")
async def google_callback(request: Request, session: SessionDep):
    """Handle Google OAuth callback"""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        if not user_info:
            raise ValueError("No user info received from Google")

        logger.debug(f"Google OAuth callback for: {user_info.get('name')}")
    except Exception as e:
        logger.error(f"Google OAuth failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="OAuth authentication failed")

    # Verify email is confirmed with Google
    if not user_info.get("email_verified", False):
        logger.warning(
            f"Unverified Google account attempted login: {user_info.get('email')}"
        )
        raise AuthenticationError("Email not verified with Google")

    email = user_info["email"]
    # Fallback to email prefix
    username = user_info.get("name", email.split("@")[0])

    # Find or create user
    user = get_user_by_email(session, email)
    if not user:
        logger.info(f"Creating new external user: {email}")
        try:
            user_create = UserCreate(username=username,
                                     email=email,
                                     avatar=user_info.get("picture"),
                                     is_external=True)
            user = create_user(session, user_create)
        except Exception as e:
            logger.error(f"Failed to create external user {email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account")

    validate_user_active(user)

    logger.info(f"External user authenticated successfully: {user.username}")
    token_pair = generate_token_pair(user.username)

    # Redirect to frontend with tokens
    redirect_url = (f"{settings.FRONTEND_CALLBACK_URL}?"
                    f"access_token={token_pair.access_token}&"
                    f"refresh_token={token_pair.refresh_token}")
    return RedirectResponse(url=redirect_url)


@router.post("/logout", summary="User logout", description="Clear user session")
async def logout(request: Request):
    """Logout user and clear session"""
    # Clear session if it exists
    if hasattr(request, 'session') and request.session:
        request.session.clear()
        logger.info("User session cleared")
    return {"message": "Successfully logged out"}


@router.get("/verify-token",
            summary="Verify access token",
            description="Validate the provided access token")
async def verify_token(current_user: CurrentUser):
    """Verify that the current access token is valid"""
    logger.debug(f"Token verified for user: {current_user.username}")
    return {
        "valid": True,
        "user": {
            "id": str(current_user.id),
            "username": current_user.username,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser
        }
    }
