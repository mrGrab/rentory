from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from pydantic import field_validator
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from models.common import TimestampMixin
from models.payment import Payment, PaymentBase, PaymentPublic

if TYPE_CHECKING:
    from models.client import Client
    from models.item_variant import ItemVariantQuantity
    from models.links import OrderItemLink


class OrderStatus(str, Enum):
    BOOKED = "booked"  # booked
    BOOKED_NOT_PAID = "booked_not_paid"  # booked, but not paid
    ISSUED = "issued"  # item(s) handed over to client
    RETURNED = "returned"  # item(s) returned
    DONE = "done"  # fully closed (checked, finalized)
    CANCELED = "canceled"  # canceled before or after booking


class PickupType(str, Enum):
    SHOWROOM = "showroom"
    TAXI = "taxi"
    POSTAL_SERVICE = "postal_service"


# ---------- EMBEDDED TYPES ----------


class DeliveryInfo(SQLModel):
    pickup_type: PickupType = PickupType.SHOWROOM
    return_type: PickupType = PickupType.SHOWROOM
    delivery_address: str | None = None
    return_address: str | None = None
    tracking_number: str | None = None


class OrderItemPublicInfo(SQLModel):
    """Public representation of an item inside an order"""

    item_id: UUID
    item_variant_id: UUID
    title: str | None = None
    size: str | None = None
    color: str | None = None
    quantity: int
    price: int
    deposit: int


# ---------- Database Model ----------


class Order(TimestampMixin, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    status: OrderStatus = Field(default=OrderStatus.BOOKED_NOT_PAID, index=True)
    client_id: UUID = Field(foreign_key="client.id", index=True)
    start_time: date = Field(index=True)
    end_time: date = Field(index=True)
    discount: int = Field(default=0, ge=0, le=100)
    deposit_amount: int = Field(default=0, ge=0)
    price: int = Field(default=0, ge=0)
    delivery_info: DeliveryInfo | None = Field(default=None, sa_column=Column(JSON))
    created_by_user_id: UUID = Field(foreign_key="user.id", index=True)
    notes: str | None = Field(default=None, max_length=1024)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    is_archived: bool = Field(default=False, index=True)
    # Quoted forward ref: Client is only imported under TYPE_CHECKING
    client: Optional["Client"] = Relationship(back_populates="orders")  # noqa: UP037, UP045
    item_links: list[OrderItemLink] = Relationship(
        back_populates="order", cascade_delete=True
    )
    payments: list[Payment] = Relationship(back_populates="order", cascade_delete=True)


# ---------- API Schemas ----------


class OrderBase(SQLModel):
    status: OrderStatus = Field(default=OrderStatus.BOOKED_NOT_PAID)
    start_time: date
    end_time: date
    discount: int = Field(default=None, ge=0, le=100)
    deposit_amount: int = Field(default=0, ge=0)
    price: int = Field(default=0, ge=0)
    delivery_info: DeliveryInfo | None = None
    notes: str | None = Field(default=None, max_length=1024)
    tags: list[str] = Field(default_factory=list)


class OrderCreate(OrderBase):
    client_id: UUID
    created_by_user_id: UUID | None = None
    items: list[ItemVariantQuantity] = Field(default_factory=list)
    payments: list[PaymentBase] | None = Field(default_factory=list)


class OrderUpdate(SQLModel):
    status: OrderStatus | None = None
    start_time: date | None = None
    end_time: date | None = None
    created_by_user_id: UUID | None = None
    discount: int | None = Field(default=None, ge=0, le=100)
    deposit_amount: int | None = Field(default=None, ge=0)
    price: int | None = Field(default=None, ge=0)
    delivery_info: DeliveryInfo | None = None
    notes: str | None = None
    tags: list[str] | None = None
    is_archived: bool | None = None
    items: list[ItemVariantQuantity] | None = None
    payments: list[PaymentBase] | None = None


class OrderPublic(OrderBase):
    id: int
    created_at: datetime
    updated_at: datetime
    client_id: UUID
    created_by_user_id: UUID
    items: list[OrderItemPublicInfo] = Field(default_factory=list)
    payments: list[PaymentPublic] = Field(default_factory=list)


class OrderFilters(SQLModel):
    id: list[int] | None = None
    status: list[OrderStatus] | None = None
    client_id: UUID | None = None
    start_time: date | None = None
    end_time: date | None = None
    tag: str | None = None
    pickup_type: PickupType | None = None
    phone: str | None = None
    item_ids: list[UUID] | None = None
    is_archived: bool | None = None
    created_at: datetime | None = None

    @field_validator("status", mode="before")
    @classmethod
    def parse_status_to_list(cls, value: Any) -> list[OrderStatus] | None:
        if value is None or value == "":
            return None

        if isinstance(value, list):
            return [OrderStatus(v) for v in value if v]
        return [OrderStatus(value)]

    @field_validator("id", mode="before")
    @classmethod
    def parse_id_to_list(cls, value: Any) -> list[int] | None:
        if value is None or value == "":
            return value

        # Accept list of IDs directly
        if isinstance(value, list):
            try:
                return [int(x) for x in value if str(x).strip() != ""]
            except ValueError, TypeError:
                return [-1]

        if isinstance(value, str) and "," in value:
            value = value.split(",")
        else:
            value = [value]

        try:
            return [int(x) for x in value if str(x).strip() != ""]
        except ValueError, TypeError:
            # Return an impossible ID like -1 so the DB finds 0 records.
            return [-1]
