from uuid import UUID

from pydantic import EmailStr
from sqlmodel import Field, SQLModel

from models.common import TimestampMixin, UUIDMixin

# ---------- Base Schemas ----------


class UserBase(SQLModel):
    username: str = Field(index=True, max_length=255)
    email: EmailStr = Field(index=True, max_length=255)
    avatar: str | None = Field(default=None, max_length=512)


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
    password: str | None = Field(min_length=8, max_length=40)
    is_external: bool = Field(default=False)


class UserRegister(SQLModel):
    username: str = Field(max_length=255)
    email: EmailStr = Field(max_length=255)
    avatar: str | None = Field(default=None, max_length=512)
    password: str = Field(min_length=8, max_length=40)
    is_external: bool = Field(default=False)


class UserUpdate(SQLModel):
    username: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    avatar: str | None = Field(default=None, max_length=512)
    password: str | None = Field(default=None, min_length=8, max_length=40)
    is_superuser: bool | None = None
    is_active: bool | None = None
    is_external: bool | None = None


class UserUpdateMe(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    avatar: str | None = Field(default=None, max_length=512)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


class UserPublic(UserBase):
    id: UUID
    is_active: bool
    is_superuser: bool
    is_external: bool


class UsersPublic(SQLModel):
    data: list[UserPublic]
    total: int


class UserFilters(SQLModel):
    id: list[UUID] | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    is_external: bool | None = None
