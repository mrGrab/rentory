from uuid import UUID
from enum import Enum
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship, Column, JSON

from models.common import TimestampMixin
from models.payment import Payment, PaymentBase, PaymentPublic

if TYPE_CHECKING:
    from models.client import Client
    from models.links import OrderItemLink
    from models.item_variant import ItemVariantQuantity

# ---------- ENUMS ----------


class OrderStatus(str, Enum):
    BOOKED = "booked"  # reserved, but payment not received
    BOOKED_PAID = "booked_paid"  # reserved and payment received
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
    delivery_address: Optional[str] = None
    return_address: Optional[str] = None
    tracking_number: Optional[str] = None


class OrderItemPublicInfo(SQLModel):
    """Public representation of an item inside an order"""
    item_id: UUID
    item_variant_id: UUID
    title: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    quantity: int
    price: int
    deposit: int


# ---------- Database Model ----------


class Order(TimestampMixin, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    status: OrderStatus = Field(default=OrderStatus.BOOKED, index=True)
    client_id: UUID = Field(foreign_key="client.id", index=True)
    start_time: date = Field(index=True)
    end_time: date = Field(index=True)
    discount: int = Field(default=0, ge=0, le=100)
    deposit_amount: int = Field(default=0, ge=0)
    price: int = Field(default=0, ge=0)
    delivery_info: Optional[DeliveryInfo] = Field(default=None,
                                                  sa_column=Column(JSON))
    created_by_user_id: UUID = Field(foreign_key="user.id", index=True)
    notes: Optional[str] = Field(default=None, max_length=1024)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    is_archived: bool = Field(default=False, index=True)

    client: Optional["Client"] = Relationship(back_populates="orders")
    item_links: List["OrderItemLink"] = Relationship(back_populates="order",
                                                     cascade_delete=True)
    payments: List[Payment] = Relationship(back_populates="order",
                                           cascade_delete=True)


# ---------- API Schemas ----------


class OrderBase(SQLModel):
    status: OrderStatus = Field(default=OrderStatus.BOOKED)
    start_time: date
    end_time: date
    discount: int = Field(default=None, ge=0, le=100)
    deposit_amount: int = Field(default=0, ge=0)
    price: int = Field(default=0, ge=0)
    delivery_info: Optional[DeliveryInfo] = None
    notes: Optional[str] = Field(default=None, max_length=1024)
    tags: List[str] = Field(default_factory=list)


class OrderCreate(OrderBase):
    client_id: UUID
    created_by_user_id: Optional[UUID] = None
    items: List["ItemVariantQuantity"] = Field(default_factory=list)
    payments: Optional[List[PaymentBase]] = Field(default_factory=list)


class OrderUpdate(SQLModel):
    status: Optional[OrderStatus] = None
    start_time: Optional[date] = None
    end_time: Optional[date] = None
    created_by_user_id: Optional[UUID] = None
    discount: Optional[int] = Field(default=None, ge=0, le=100)
    deposit_amount: Optional[int] = Field(default=None, ge=0)
    price: Optional[int] = Field(default=None, ge=0)
    delivery_info: Optional[DeliveryInfo] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    is_archived: Optional[bool] = None
    items: Optional[List["ItemVariantQuantity"]] = None
    payments: Optional[List[PaymentBase]] = None


class OrderPublic(OrderBase):
    id: int
    created_at: datetime
    updated_at: datetime
    client_id: UUID
    created_by_user_id: UUID
    items: List["OrderItemPublicInfo"] = Field(default_factory=list)
    payments: List[PaymentPublic] = Field(default_factory=list)


class OrderFilters(SQLModel):
    id: Optional[List[int]] = None
    status: Optional[OrderStatus] = None
    client_id: Optional[UUID] = None
    start_time: Optional[date] = None
    end_time: Optional[date] = None
    tag: Optional[str] = None
    pickup_type: Optional[PickupType] = None
    phone: Optional[str] = None
    item_ids: Optional[List[UUID]] = None
    is_archived: Optional[bool] = None
    created_at: Optional[datetime] = None
