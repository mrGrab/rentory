from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, EmailStr
from pydantic_extra_types.phone_numbers import PhoneNumber
from sqlmodel import Field, Relationship, SQLModel

from models.common import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from models.order import Order


class Phone(PhoneNumber):
    phone_format = "E164"


# ---------- Database Model ----------


class Client(UUIDMixin, TimestampMixin, table=True):
    """Represents a customer in the system"""

    given_name: str | None = Field(max_length=255, index=True)
    surname: str | None = Field(max_length=255)
    phone: Phone = Field(unique=True, max_length=20, index=True)
    instagram: str | None = Field(max_length=255, index=True)
    email: EmailStr | None = Field(max_length=255, index=True)
    notes: str | None = Field(max_length=512)
    discount: int | None = Field(default=None, ge=0, le=100)
    is_archived: bool = Field(default=False)
    is_trusted: bool = Field(default=False)

    orders: list[Order] = Relationship(back_populates="client")


# ---------- API Schemas ----------


class ClientBase(SQLModel):
    given_name: str | None = None
    surname: str | None = None
    phone: Phone | None = None
    instagram: str | None = None
    email: EmailStr | None = None
    notes: str | None = None
    discount: int | None = Field(default=None, ge=0, le=100)
    is_trusted: bool = False


class ClientCreate(ClientBase):
    """Data for creating a new client"""

    phone: Phone


class ClientUpdate(ClientBase):
    """Partial update for existing client"""

    is_archived: bool | None = None


class ClientPublic(ClientBase):
    """Public-facing representation of a client"""

    id: UUID
    order_ids: list[int] = Field(default_factory=list)


class ClientFilters(BaseModel):
    """Filter options for searching clients"""

    id: list[UUID] | None = None
    phone: str | None = None
    instagram: str | None = None
    email: str | None = None
    given_name: str | None = None
    surname: str | None = None
    discount: int | None = None
    is_archived: bool | None = None
    is_trusted: bool | None = None
