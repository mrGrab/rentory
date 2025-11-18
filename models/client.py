from uuid import UUID
from pydantic import EmailStr, BaseModel, field_serializer
from pydantic_extra_types.phone_numbers import PhoneNumber

from typing import Optional, List, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

from models.common import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from models.order import Order


class Phone(PhoneNumber):
    phone_format = 'E164'


# ---------- Database Model ----------


class Client(UUIDMixin, TimestampMixin, table=True):
    """Represents a customer in the system"""

    given_name: Optional[str] = Field(max_length=255, index=True)
    surname: Optional[str] = Field(max_length=255)
    phone: Phone = Field(unique=True, max_length=20, index=True)
    instagram: Optional[str] = Field(max_length=255, index=True)
    email: Optional[EmailStr] = Field(max_length=255, index=True)
    notes: Optional[str] = Field(max_length=512)
    discount: Optional[int] = Field(default=None, ge=0, le=100)
    is_archived: bool = Field(default=False)

    orders: List["Order"] = Relationship(back_populates="client")


# ---------- API Schemas ----------


class ClientBase(SQLModel):
    given_name: Optional[str] = None
    surname: Optional[str] = None
    phone: Optional[Phone] = None
    instagram: Optional[str] = None
    email: Optional[EmailStr] = None
    notes: Optional[str] = None
    discount: Optional[int] = Field(default=None, ge=0, le=100)


class ClientCreate(ClientBase):
    """Data for creating a new client"""
    phone: Phone


class ClientUpdate(ClientBase):
    """Partial update for existing client"""
    is_archived: Optional[bool] = None


class ClientPublic(ClientBase):
    """Public-facing representation of a client"""
    id: UUID
    order_ids: List[int] = Field(default_factory=list)


class ClientFilters(BaseModel):
    """Filter options for searching clients"""

    id: Optional[List[UUID]] = None
    phone: Optional[str] = None
    instagram: Optional[str] = None
    email: Optional[str] = None
    given_name: Optional[str] = None
    surname: Optional[str] = None
    discount: Optional[int] = None
    is_archived: Optional[bool] = None
