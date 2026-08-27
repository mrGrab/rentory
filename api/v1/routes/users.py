# coding: UTF-8
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from core.database import SessionDep
from core.dependencies import CurrentSuperuser, CurrentUser
from core.exceptions import NotFoundException
from core.logger import logger

# --- Project Imports ---
from core.query_utils import calculate_pagination, parse_params, set_pagination_headers
from models.user import User, UserCreate, UserFilters, UserPublic, UserUpdate
from services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

# ---------- Helper Functions ----------


def get_user_service(session: SessionDep) -> UserService:
    """Dependency to get UserService instance"""
    return UserService(session)


def get_user_or_404(
    user_id: UUID, service: Annotated[UserService, Depends(get_user_service)]
) -> User:
    """Dependency to retrieve a user by ID or raise NotFoundException"""
    user = service.get_by_id(user_id)
    if not user:
        logger.warning(f"User not found: {user_id}")
        raise NotFoundException(f"User with ID {user_id} not found")
    return user


# ---------- Routes ----------


@router.get(
    "",
    response_model=list[UserPublic],
    summary="List all users",
    description="Retrieve a paginated list of all users. Available to all authenticated users.",
)
def list_users(
    response: Response,
    current_user: CurrentUser,
    service: Annotated[UserService, Depends(get_user_service)],
    filter_: Annotated[str, Query(alias="filter")] = "{}",
    range_: Annotated[str, Query(alias="range")] = "[0, 500]",
    sort: Annotated[str, Query(alias="sort")] = '["id","DESC"]',
):
    """List users with filtering, sorting, and pagination"""
    logger.debug(f"User {current_user.username} listing users")

    params = parse_params(filter_, range_, sort)
    filters = UserFilters(**params.filters)
    offset, limit = calculate_pagination(params.range_list)

    users, total = service.get_users(
        filters=filters,
        offset=offset,
        limit=limit,
        sort_field=params.sort_field,
        sort_order=params.sort_order,
    )

    result = [UserPublic.model_validate(user) for user in users]
    set_pagination_headers(response, offset, len(result), total)

    logger.info(f"Fetched {len(result)} users out of {total} total")
    return result


@router.post(
    "",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (superuser only)",
    description="Create a new user account. Requires superuser privileges.",
)
def create_user(
    user_in: UserCreate,
    current_user: CurrentSuperuser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """Create a new user account"""
    logger.debug(f"User {current_user.username} creating user")

    user = service.create(user_in)
    logger.info(f"User {current_user.username} created user {user.id}")
    return UserPublic.model_validate(user)


@router.get(
    "/me",
    summary="Get current user profile",
    description="Return the authenticated user's profile data",
)
def read_current_user(current_user: CurrentUser) -> UserPublic:
    """Get the current authenticated user's profile"""
    logger.debug(f"Fetching profile for current user: {current_user.username}")
    return UserPublic.model_validate(current_user)


@router.get(
    "/{user_id}",
    response_model=UserPublic,
    summary="Get user by ID",
    description="Retrieve a user's profile by their ID. Available to all authenticated users.",
)
def read_user_by_id(
    current_user: CurrentUser, user: Annotated[User, Depends(get_user_or_404)]
):
    """Get a specific user by ID"""
    logger.info(f"User {current_user.username} retrieved user {user.id}")
    return UserPublic.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserPublic,
    summary="Update user (superuser only)",
    description="Update a user's details. Requires superuser privileges.",
)
def update_user(
    user_in: UserUpdate,
    current_user: CurrentSuperuser,
    service: Annotated[UserService, Depends(get_user_service)],
    user: Annotated[User, Depends(get_user_or_404)],
):
    """Update a user's details"""
    logger.debug(f"Superuser {current_user.username} updating user {user.id}")
    updated = service.update(user, user_in)
    logger.info(f"Superuser {current_user.username} updated user {updated.id}")
    return UserPublic.model_validate(updated)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user (superuser only)",
    description="Permanently delete a user. Requires superuser privileges.",
)
def delete_user(
    current_user: CurrentSuperuser,
    service: Annotated[UserService, Depends(get_user_service)],
    user: Annotated[User, Depends(get_user_or_404)],
):
    """Delete a user permanently"""
    logger.debug(f"Superuser {current_user.username} deleting user {user.id}")
    service.delete(user)
    logger.info(f"Superuser {current_user.username} deleted user {user.id}")
