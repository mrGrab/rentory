# coding: UTF-8
import uuid
from sqlmodel import select
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

# --- Project Imports ---
import core.query_utils as qp
from core.logger import logger
from core.models import UserCreate, UserPublic, User, UserFilters
from core.dependencies import CurrentUser, get_current_superuser
from core.database import (
    SessionDep,
    create_user,
    get_user_by_username,
    get_user_by_email,
)
from core.exceptions import (
    InternalErrorException,
    NotFoundException,
    ConflictException,
)

router = APIRouter(prefix="/users", tags=["Users"])


def check_user_exists(session: SessionDep, username: str, email: str) -> bool:
    """Check if user already exists by username or email"""
    if get_user_by_username(session, username):
        return True
    if get_user_by_email(session, email):
        return True
    return False


def apply_filters(stmt, filters: UserFilters):
    """Apply user filters to the query statement"""
    if filters.id:
        if isinstance(filters.id, list):
            stmt = stmt.where(User.id.in_(filters.id))
        else:
            stmt = stmt.where(User.id.contains(filters.id))

    if filters.is_external:
        stmt = stmt.where(User.is_external == True)

    if filters.is_active:
        stmt = stmt.where(User.is_active == True)

    if filters.is_superuser:
        stmt = stmt.where(User.is_superuser == True)

    return stmt


@router.get("",
            response_model=list[UserPublic],
            summary="List all users",
            description="Retrieve a paginated list of all users",
            dependencies=[Depends(get_current_superuser)])
def read_users(response: Response,
               session: SessionDep,
               filter_: str = Query("{}", alias="filter"),
               range_: str = Query("[0, 500]", alias="range"),
               sort: str = Query('["id","DESC"]', alias="sort")):
    """List users with filtering, sorting, and pagination"""

    try:
        # Parse query parameters
        filter_dict, range_list, sort_field, sort_order = qp.parse_params(
            filter_, range_, sort)

        # Build filters
        filters = UserFilters(**filter_dict)
        offset, limit = qp.calculate_pagination(range_list)

        # Build query
        stmt = select(User)
        stmt = apply_filters(stmt, filters)
        stmt = qp.apply_sorting(stmt, User, sort_field, sort_order)

        # Get total count before pagination
        total = qp.get_total_count(session, stmt)

        # Apply pagination and execute
        stmt = stmt.offset(offset).limit(limit)
        users = session.exec(stmt).all()

        result = [UserPublic.model_validate(user) for user in users]
        qp.set_pagination_headers(response, offset, len(result), total)

        logger.info(f"Fetched {len(result)} users out of {total} total")
        return result

    except HTTPException:
        raise  # Re-raise HTTP exceptions from parse_params
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise InternalErrorException("Failed to retrieve users")


@router.post("",
             response_model=UserPublic,
             status_code=status.HTTP_201_CREATED,
             summary="Create a new user",
             description="Register a new user account",
             dependencies=[Depends(get_current_superuser)])
def create_new_user(session: SessionDep, user_in: UserCreate) -> UserPublic:
    """Create a new user account"""
    logger.debug(f"Creating new user: {user_in.username}")

    # Check if user already exists
    if check_user_exists(session, user_in.username, user_in.email):
        logger.warning(
            f"User creation failed - already exists: {user_in.username}")
        raise ConflictException("User already exists")

    # Create the user
    try:
        user = create_user(session, user_in)
        logger.info(f"Successfully created user: {user.username}")
        return UserPublic.model_validate(user)
    except HTTPException:
        raise  # Re-raise HTTP exceptions from create_user
    except Exception as e:
        logger.error(f"Unexpected error creating user {user_in.username}: {e}")
        raise InternalErrorException("Failed to create user account")


@router.get("/me",
            response_model=UserPublic,
            summary="Get current user profile",
            description="Return the authenticated user's profile data")
def read_current_user(current_user: CurrentUser) -> UserPublic:
    """Get the current authenticated user's profile"""
    logger.debug(f"Fetching profile for current user: {current_user.username}")
    return UserPublic.model_validate(current_user)


@router.get("/{user_id}",
            response_model=UserPublic,
            summary="Get user by ID",
            description="Retrieve a user's profile by their ID",
            dependencies=[Depends(get_current_superuser)])
def read_user_by_id(user_id: uuid.UUID, session: SessionDep) -> UserPublic:
    """Get a specific user by ID"""
    logger.debug(f"Fetching user {user_id}")

    # Get the user
    user = session.get(User, user_id)
    if not user:
        logger.warning(f"User not found: {user_id}")
        raise NotFoundException("User not found")

    logger.debug(f"Successfully retrieved user: {user.username}")
    return UserPublic.model_validate(user)
