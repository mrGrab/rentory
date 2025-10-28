from uuid import UUID, uuid4
from enum import Enum
from datetime import datetime, date, timezone
from typing import Optional, List
from pydantic import EmailStr, BaseModel
from sqlmodel import Field, SQLModel, Relationship, Column, JSON


# --------------------
# Shared mixins
# --------------------
class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class UUIDMixin(SQLModel):
    id: UUID | None = Field(default_factory=uuid4, primary_key=True, index=True)


# --------------------
# Link Models
# --------------------
class OrderItemLink(SQLModel, table=True):
    order_id: int = Field(foreign_key="order.id",
                          primary_key=True,
                          ondelete="CASCADE")
    item_variant_id: UUID = Field(foreign_key="itemvariant.id",
                                  primary_key=True)
    price: int = Field(default=0, ge=0)
    quantity: int = Field(default=1, ge=1)
    order: Optional["Order"] = Relationship(back_populates="item_links")
    item_variant: Optional["ItemVariant"] = Relationship(
        back_populates="order_links")


# --------------------
# User models
# --------------------
class UserBase(SQLModel):
    username: str = Field(unique=True, index=True, max_length=255)
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    avatar: Optional[str] = Field(default=None, max_length=512)


class UserCreate(UserBase):
    password: Optional[str] = Field(default=None, min_length=8, max_length=40)
    is_external: bool = Field(default=False)


class UserRegister(SQLModel):
    username: str = Field(max_length=255)
    email: EmailStr = Field(max_length=255)
    avatar: Optional[str] = Field(default=None, max_length=512)
    password: str = Field(min_length=8, max_length=40)
    is_external: bool = Field(default=False)


class UserUpdate(UserBase):
    username: Optional[str] = Field(default=None, max_length=255)
    email: Optional[EmailStr] = Field(default=None, max_length=255)
    avatar: Optional[str] = Field(default=None, max_length=512)
    password: Optional[str] = Field(default=None, min_length=8, max_length=40)
    is_superuser: Optional[bool] = None
    is_active: Optional[bool] = None
    is_external: Optional[bool] = None


class UserUpdateMe(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    avatar: Optional[str] = Field(default=None, max_length=512)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


class User(UserBase, UUIDMixin, TimestampMixin, table=True):
    hashed_password: str
    is_superuser: bool = Field(default=False)
    is_active: bool = Field(default=False)
    is_external: bool = Field(default=False)


class UserPublic(UserBase):
    id: UUID
    is_active: bool
    is_superuser: bool
    is_external: bool


class UsersPublic(SQLModel):
    data: list[UserPublic]
    total: int


class UserFilters(SQLModel):
    id: Optional[List[UUID] | UUID] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_external: Optional[bool] = None


# --------------------
# Item models
# --------------------
class ItemVariantStatus(str, Enum):
    AVAILABLE = "available"
    CLEANING = "cleaning"
    REPAIR = "repair"
    UNAVAILABLE = "unavailable"


class ItemStatus(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"


# Table Models
class Item(UUIDMixin, TimestampMixin, SQLModel, table=True):
    title: str = Field(index=True, unique=True, max_length=255)
    category: Optional[str] = Field(default=None, index=True, max_length=100)
    description: Optional[str] = Field(default=None, max_length=512)
    image_url: Optional[str] = Field(default=None, max_length=512)
    status: ItemStatus = Field(default=ItemStatus.IN_STOCK, index=True)
    tags: Optional[List[str]] = Field(default_factory=list,
                                      sa_column=Column(JSON))
    variants: List["ItemVariant"] = Relationship(back_populates="item",
                                                 cascade_delete=True)


class ItemVariant(UUIDMixin, TimestampMixin, SQLModel, table=True):
    item_id: UUID = Field(foreign_key="item.id")
    stock_quantity: int = Field(default=1, ge=0)
    size: Optional[str] = Field(default=None, max_length=50)
    color: Optional[str] = Field(default=None, max_length=50)
    status: ItemVariantStatus = Field(default=ItemVariantStatus.AVAILABLE,
                                      index=True)
    service_start_time: Optional[date] = None
    service_end_time: Optional[date] = None
    is_active: bool = Field(default=True)
    item: "Item" = Relationship(back_populates="variants")
    prices: List["ItemPrice"] = Relationship(back_populates="variant",
                                             cascade_delete=True)
    order_links: List["OrderItemLink"] = Relationship(
        back_populates="item_variant")


class ItemPrice(UUIDMixin, SQLModel, table=True):
    variant_id: UUID = Field(foreign_key="itemvariant.id")
    amount: int = Field(default=0, ge=0)
    deposit: int = Field(default=0, ge=0)
    price_type: Optional[str] = Field(default=None, max_length=100)
    variant: "ItemVariant" = Relationship(back_populates="prices")


# Pydantic Schemas (for API I/O)
class ItemVariantQuantity(BaseModel):
    item_id: UUID
    item_variant_id: UUID
    quantity: int = Field(default=1, ge=1)
    price: int = Field(default=0, ge=0)


class ItemPriceBase(SQLModel):
    amount: int
    deposit: int = Field(default=0, ge=0)
    price_type: Optional[str] = None


class ItemVariantBase(UUIDMixin, SQLModel):
    size: Optional[str] = None
    color: Optional[str] = None
    status: ItemVariantStatus = ItemVariantStatus.AVAILABLE
    service_start_time: Optional[date] = None
    service_end_time: Optional[date] = None
    stock_quantity: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)
    prices: List[ItemPriceBase] = []


class ItemVariantUpdate(UUIDMixin, SQLModel):
    size: Optional[str] = None
    color: Optional[str] = None
    status: Optional[ItemVariantStatus] = None
    service_start_time: Optional[date] = None
    service_end_time: Optional[date] = None
    stock_quantity: Optional[int] = None


class ItemVariantPublic(ItemVariantBase):
    item_id: UUID


class ItemVariantsPublic(SQLModel):
    data: List[ItemVariantPublic]
    total: int


class ItemVariantFilters(SQLModel):
    id: Optional[List[UUID]] = None
    item_id: Optional[List[UUID]] = None
    size: Optional[str] = None
    color: Optional[str] = None
    status: Optional[List[ItemVariantStatus]] = None
    service_start_time: Optional[date] = None
    service_end_time: Optional[date] = None


class ItemBase(SQLModel):
    title: str = Field(max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=512)
    image_url: Optional[str] = None
    status: ItemStatus = ItemStatus.IN_STOCK
    tags: List[str] = []


class ItemCreate(ItemBase):
    variants: List[ItemVariantBase] = []


class ItemUpdate(SQLModel):
    title: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=512)
    image_url: Optional[str] = None
    status: Optional[ItemStatus] = None
    tags: Optional[List[str]] = None
    variants: List[ItemVariantBase] = []


class ItemPublic(ItemBase):
    id: UUID
    variants: List[ItemVariantBase] = []
    order_ids: List[int] = []


class ItemsPublic(SQLModel):
    data: List[ItemPublic]
    total: int


class ItemFilters(SQLModel):
    id: Optional[List[UUID] | UUID] = None
    title: Optional[str] = None
    category: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    status: Optional[ItemStatus] = None
    variant_status: Optional[ItemVariantStatus] = None
    tag: Optional[str] = None
    q: Optional[str] = None


# --------------------
# Client models
# --------------------
class ClientBase(SQLModel):
    given_name: Optional[str] = Field(default=None, index=True, max_length=255)
    surname: Optional[str] = Field(default=None, max_length=255)
    phone: str = Field(index=True, unique=True, max_length=20)
    instagram: Optional[str] = Field(default=None, max_length=255)
    email: Optional[EmailStr] = Field(default=None, index=True, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=512)


class ClientCreate(ClientBase):
    discount: Optional[int] = Field(default=None, ge=0, le=100)


class ClientUpdate(SQLModel):
    given_name: Optional[str] = Field(default=None, index=True, max_length=255)
    surname: Optional[str] = Field(default=None, max_length=255)
    phone: str = Field(index=True, max_length=20)
    instagram: Optional[str] = Field(default=None, max_length=255)
    email: Optional[EmailStr] = Field(default=None, index=True, max_length=255)
    discount: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=512)


class Client(ClientBase, UUIDMixin, TimestampMixin, table=True):
    discount: Optional[int] = Field(default=None, ge=0, le=100)
    orders: List["Order"] = Relationship(back_populates="client")


class ClientPublic(ClientBase):
    """Public API representation of a client."""
    id: UUID
    discount: Optional[int] = None
    order_ids: List[int] = []


class ClientFilters(BaseModel):
    """Filters available for querying clients."""
    id: Optional[List[UUID]] = None
    phone: Optional[str] = None
    instagram: Optional[str] = None
    email: Optional[str] = None
    given_name: Optional[str] = None
    surname: Optional[str] = None
    discount: Optional[int] = None


# --------------------
# Order models
# --------------------
class OrderStatus(str, Enum):
    BOOKED = "booked"
    ISSUED = "issued"
    RETURNED = "returned"
    DONE = "done"
    CANCELED = "canceled"


class PaymentType(str, Enum):
    CASH = "cash"
    CARD = "card"
    DEPOSIT = "deposit"
    BANK_TRANSFER = "bank_transfer"


class PickupType(str, Enum):
    SHOWROOM = "showroom"
    TAXI = "taxi"
    POSTAL_SERVICE = "postal_service"


# Payment & Delivery Details
class PaymentDetails(BaseModel):
    total: int = Field(default=0, ge=0)
    paid: int = Field(default=0, ge=0)
    deposit: int = Field(default=0, ge=0)
    payment_type: PaymentType = PaymentType.CARD
    transaction_id: Optional[str] = None


class DeliveryInfo(BaseModel):
    pickup_type: PickupType = PickupType.SHOWROOM
    address: Optional[str] = None
    tracking_number: Optional[str] = None


# Order
class OrderItemPublicInfo(BaseModel):
    item_id: UUID
    item_variant_id: UUID
    size: Optional[str] = None
    color: Optional[str] = None
    status: ItemVariantStatus = ItemVariantStatus.AVAILABLE
    quantity: int
    price: int


class OrderBase(SQLModel):
    status: OrderStatus = Field(default=OrderStatus.BOOKED, index=True)
    start_time: Optional[date] = Field(default=None)
    end_time: Optional[date] = Field(default=None)
    order_discount: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=1024)
    tags: Optional[List[str]] = Field(default_factory=list,
                                      sa_column=Column(JSON))
    delivery_info: Optional[DeliveryInfo] = Field(default=None,
                                                  sa_column=Column(JSON))
    payment_details: Optional[PaymentDetails] = Field(default=None,
                                                      sa_column=Column(JSON))


class OrderCreate(OrderBase):
    client_id: UUID
    items: List[ItemVariantQuantity] = Field(default_factory=list)


class OrderUpdate(SQLModel):
    client_id: Optional[UUID] = None
    status: Optional[OrderStatus] = None
    start_time: Optional[date] = None
    end_time: Optional[date] = None
    order_discount: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=1024)
    tags: List[str] = Field(default_factory=list)
    delivery_info: Optional[DeliveryInfo] = None
    payment_details: Optional[PaymentDetails] = None
    items: Optional[List[ItemVariantQuantity]] = None


class Order(TimestampMixin, OrderBase, table=True):
    id: int | None = Field(default_factory=None, primary_key=True, index=True)
    created_by_user_id: UUID = Field(foreign_key="user.id", index=True)
    client_id: UUID = Field(foreign_key="client.id", index=True)
    client: Optional["Client"] = Relationship(back_populates="orders")
    item_links: List["OrderItemLink"] = Relationship(back_populates="order",
                                                     cascade_delete=True)


class OrderPublic(OrderBase):
    id: int
    created_at: datetime
    updated_at: datetime
    client_id: UUID
    created_by_user_id: UUID
    items: List[OrderItemPublicInfo] = []


class OrderFilters(SQLModel):
    id: Optional[List[int] | int] = None
    status: Optional[OrderStatus] = None
    client_id: Optional[UUID] = None
    phone: Optional[str] = None
    start_time: Optional[date] = None
    end_time: Optional[date] = None
    tag: Optional[str] = None
    item_ids: Optional[List[UUID]] = None
    pickup_type: Optional[PickupType] = None


# --------------------
# Auth models
# --------------------
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None


class TokenPayload(SQLModel):
    sub: str | None = None
    exp: Optional[int] = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
