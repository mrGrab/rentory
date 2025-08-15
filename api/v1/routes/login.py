from datetime import timedelta
from typing import Annotated

from fastapi import Depends, APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from core.config import settings
from core.logger import logger
from core.models import Token
from core.dependency import authenticate_user, create_access_token, SessionDep

router = APIRouter(tags=["Login"])


@router.post("/login/access-token",
             response_model=Token,
             summary="User login to receive access token",
             description="Authenticate a user and return a JWT access token.")
def login_access_token(form_data: Annotated[OAuth2PasswordRequestForm,
                                            Depends()],
                       session: SessionDep) -> Token:
    logger.debug(f"Login attempt for user: {form_data.username}")

    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        logger.warning(
            f"Login failed: {form_data.username} - invalid credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})

    if not user.is_active:
        logger.warning(f"Login failed: {form_data.username} - account inactive")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Inactive user",
                            headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = create_access_token(data={"sub": user.username},
                                       expires_delta=access_token_expires)
    logger.info(f"Access token issued for user: {user.username}")
    return Token(access_token=access_token, token_type="bearer")
