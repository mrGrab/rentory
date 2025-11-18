# coding: UTF-8
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response, status

# --- Project Imports ---
from core.query_utils import parse_params, calculate_pagination, set_pagination_headers
from core.logger import logger
from core.dependencies import CurrentUser
from core.database import SessionDep
from core.exceptions import NotFoundException
from models.user import UserCreate, UserPublic, User, UserFilters
from services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

# ---------- Helper Functions ----------


def get_user_service(session: SessionDep) -> UserService:
    """Dependency to get UserService instance"""
    return UserService(session)


def get_user_or_404(
    user_id: UUID, service: UserService = Depends(get_user_service)) -> User:
    """Dependency to retrieve a user by ID or raise NotFoundException"""
    user = service.get_by_id(user_id)
    if not user:
        logger.warning(f"User not found: {user_id}")
        raise NotFoundException(f"User with ID {user_id} not found")
    return user


# ---------- Routes ----------


@router.get("",
            response_model=list[UserPublic],
            summary="List all users",
            description="Retrieve a paginated list of all users")
def list_users(response: Response,
               current_user: CurrentUser,
               service: UserService = Depends(get_user_service),
               filter_: str = Query("{}", alias="filter"),
               range_: str = Query("[0, 500]", alias="range"),
               sort: str = Query('["id","DESC"]', alias="sort")):
    """List users with filtering, sorting, and pagination"""
    logger.debug(f"User {current_user.username} listing users")

    params = parse_params(filter_, range_, sort)
    filters = UserFilters(**params.filters)
    offset, limit = calculate_pagination(params.range_list)

    users, total = service.get_users(filters=filters,
                                     offset=offset,
                                     limit=limit,
                                     sort_field=params.sort_field,
                                     sort_order=params.sort_order)

    result = [UserPublic.model_validate(user) for user in users]
    set_pagination_headers(response, offset, len(result), total)

    logger.info(f"Fetched {len(result)} users out of {total} total")
    return result


@router.post("",
             response_model=UserPublic,
             status_code=status.HTTP_201_CREATED,
             summary="Create a new user",
             description="Register a new user account")
def create_user(user_in: UserCreate,
                current_user: CurrentUser,
                service: UserService = Depends(get_user_service)):
    """Create a new user account"""
    logger.debug(f"User {current_user.username} creating user")

    user = service.create_user(user_in)
    logger.info(f"User {current_user.username} created user {user.id}")
    return UserPublic.model_validate(user)


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
            description="Retrieve a user's profile by their ID")
def read_user_by_id(current_user: CurrentUser,
                    user: User = Depends(get_user_or_404)):
    """Get a specific user by ID"""
    logger.info(f"User {current_user.username} retrieved user {user.id}")
    return UserPublic.model_validate(user)
