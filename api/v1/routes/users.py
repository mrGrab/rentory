# coding: UTF-8

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func
from core.logger import logger
from core.dependency import (
    SessionDep,
    CurrentUser,
    get_user_by_email,
    hash_password,
    get_user_by_username,
    get_current_superuser,
)
from core.models import (
    UserCreate,
    UserPublic,
    User,
    UsersPublic,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("",
            response_model=UsersPublic,
            summary="List all users",
            description="Retrieve a paginated list of all users",
            dependencies=[Depends(get_current_superuser)])
def read_users(session: SessionDep,
               offset: int = Query(0, ge=0),
               limit: int = Query(10, ge=1, le=100)):
    logger.debug(f"Fetching users with offset={offset}, limit={limit}")
    try:
        count_stmt = select(func.count()).select_from(User)
        total = session.exec(count_stmt).one()

        stmt = select(User).offset(offset).limit(limit)
        raw_users = session.exec(stmt).all()

        users = [UserPublic.model_validate(i) for i in raw_users]
        logger.info(f"Fetched {len(users)} users out of {total} total")
        return UsersPublic(data=users, total=total)
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve users")


@router.post(
    "",
    response_model=UserPublic,
    summary="Create a new user",
    description="Registers a new user account.",
    dependencies=[Depends(get_current_superuser)],
)
def create_user(session: SessionDep, user_in: UserCreate) -> UserPublic:
    # Check if email already exists
    if get_user_by_email(session, user_in.email):
        logger.warning(
            f"User creation failed: email '{user_in.email}' already exists")
        raise HTTPException(status_code=400,
                            detail="A user with this email already exists")

    # Check if username already exists
    if user_in.username and get_user_by_username(session, user_in.username):
        logger.warning(
            f"User creation failed: username '{user_in.username}' already exists"
        )
        raise HTTPException(status_code=400,
                            detail="A user with this name already exists")

    # Create the user
    now = datetime.now(timezone.utc)
    user_data = user_in.model_dump(exclude={"password"})
    hashed_pw = hash_password(user_in.password)
    user = User(**user_data,
                hashed_password=hashed_pw,
                created_at=now,
                updated_at=now)
    session.add(user)
    session.commit()
    session.refresh(user)

    logger.info(f"User created: username='{user.username}'")
    return UserPublic.model_validate(user)


@router.get("/me",
            response_model=UserPublic,
            summary="Get current user profile",
            description="Returns the authenticated user's public profile data.",
            response_model_exclude_unset=True)
def read_user_me(current_user: CurrentUser) -> UserPublic:
    logger.debug(f"Returning profile for current user: {current_user.username}")
    return UserPublic.model_validate(current_user)


@router.get("/{user_id}",
            response_model=UserPublic,
            summary="Get user by ID",
            description="Retrieve a user's public profile by their ID.")
def read_user_by_id(user_id: uuid.UUID, session: SessionDep,
                    current_user: CurrentUser) -> UserPublic:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this user",
        )
    return UserPublic.model_validate(user)
