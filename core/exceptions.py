"""
This module defines custom, reusable exception classes
to ensure consistent error responses.
"""
from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base exception class to ensure consistent error responses."""

    def __init__(self,
                 status_code: int,
                 detail: str,
                 headers: dict | None = None):
        super().__init__(status_code=status_code,
                         detail=detail,
                         headers=headers)


class BadRequestException(AppException):
    """Exception for HTTP 400 Bad Request errors."""

    def __init__(self, detail: str = "Bad Request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class AuthenticationException(AppException):
    """Exception for HTTP 401 Unauthorized errors."""

    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionException(AppException):
    """Exception for HTTP 403 Forbidden errors."""

    def __init__(
            self,
            detail: str = "You do not have permission to perform this action"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundException(AppException):
    """Exception for HTTP 404 Not Found errors."""

    def __init__(self, detail: str = "The requested resource was not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictException(AppException):
    """Exception for HTTP 409 Conflict errors."""

    def __init__(self, detail: str = "Conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class InternalErrorException(AppException):
    """Exception for HTTP 500 Internal Server Error."""

    def __init__(self, detail: str = "An unexpected internal error occurred"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                         detail=detail)
