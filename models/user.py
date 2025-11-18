from uuid import UUID
from typing import Optional, List
from pydantic import EmailStr
from sqlmodel import Field, SQLModel

from models.common import UUIDMixin, TimestampMixin

# ---------- Base Schemas ----------


class UserBase(SQLModel):
    username: str = Field(index=True, max_length=255)
    email: EmailStr = Field(index=True, max_length=255)
    avatar: Optional[str] = Field(default=None, max_length=512)


# ---------- Database Model ----------


class User(UserBase, UUIDMixin, TimestampMixin, table=True):
    username: str = Field(unique=True, index=True, max_length=255)
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    hashed_password: str
    is_superuser: bool = Field(default=False)
    is_active: bool = Field(default=False)
    is_external: bool = Field(default=False)


# ---------- API Schemas ----------


class UserCreate(UserBase):
    password: Optional[str] = Field(min_length=8, max_length=40)
    is_external: bool = Field(default=False)


class UserRegister(SQLModel):
    username: str = Field(max_length=255)
    email: EmailStr = Field(max_length=255)
    avatar: Optional[str] = Field(default=None, max_length=512)
    password: str = Field(min_length=8, max_length=40)
    is_external: bool = Field(default=False)


class UserUpdate(SQLModel):
    username: Optional[str] = Field(default=None, max_length=255)
    email: Optional[EmailStr] = Field(default=None, max_length=255)
    avatar: Optional[str] = Field(default=None, max_length=512)
    password: Optional[str] = Field(default=None, min_length=8, max_length=40)
    is_superuser: Optional[bool] = None
    is_active: Optional[bool] = None
    is_external: Optional[bool] = None


class UserUpdateMe(SQLModel):
    email: Optional[EmailStr] = Field(default=None, max_length=255)
    avatar: Optional[str] = Field(default=None, max_length=512)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


class UserPublic(UserBase):
    id: UUID
    is_active: bool
    is_superuser: bool
    is_external: bool


class UsersPublic(SQLModel):
    data: List[UserPublic]
    total: int


class UserFilters(SQLModel):
    id: Optional[List[UUID]] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_external: Optional[bool] = None
