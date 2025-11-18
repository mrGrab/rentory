from uuid import UUID
from enum import Enum
from datetime import date
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

from models.common import UUIDMixin, TimestampMixin
if TYPE_CHECKING:
    from models.item import Item
    from models.links import OrderItemLink

# ---------- ENUMS ----------


class ItemVariantStatus(str, Enum):
    AVAILABLE = "available"
    CLEANING = "cleaning"
    REPAIR = "repair"
    UNAVAILABLE = "unavailable"


# ---------- Database Model ----------


class ItemVariantPrice(UUIDMixin, SQLModel, table=True):
    """Represents a price entry for a specific variant"""
    amount: int = Field(default=0, ge=0)
    deposit: int = Field(default=0, ge=0)
    price_type: Optional[str] = Field(default=None, max_length=100)

    variant_id: UUID = Field(foreign_key="itemvariant.id", index=True)
    variant: Optional["ItemVariant"] = Relationship(back_populates="prices")


class ItemVariant(UUIDMixin, TimestampMixin, SQLModel, table=True):
    """Represents a specific variant of an item (e.g., size M, color Red)"""
    quantity: int = Field(default=1, ge=0)
    size: Optional[str] = Field(default=None, max_length=50)
    color: Optional[str] = Field(default=None, max_length=50)
    service_start_time: Optional[date] = None
    service_end_time: Optional[date] = None
    is_archived: bool = Field(default=False, index=True)
    status: ItemVariantStatus = Field(default=ItemVariantStatus.AVAILABLE,
                                      index=True)

    item_id: UUID = Field(foreign_key="item.id", index=True)
    item: Optional["Item"] = Relationship(back_populates="variants")
    prices: List["ItemVariantPrice"] = Relationship(back_populates="variant",
                                                    cascade_delete=True)
    order_links: List["OrderItemLink"] = Relationship(
        back_populates="item_variant")


# ---------- Database Model ----------


class ItemVariantPriceBase(SQLModel):
    id: Optional[UUID] = None
    amount: int
    deposit: Optional[int] = Field(default=0, ge=0)
    price_type: Optional[str] = None


class ItemVariantBase(SQLModel):
    """Base schema for item variants"""
    size: Optional[str] = Field(default=None, max_length=50)
    color: Optional[str] = Field(default=None, max_length=50)
    status: ItemVariantStatus = Field(default=ItemVariantStatus.AVAILABLE)
    quantity: int = Field(default=1, ge=0)
    service_start_time: Optional[date] = None
    service_end_time: Optional[date] = None
    prices: List[ItemVariantPriceBase] = Field(default_factory=list)


class ItemVariantCreate(ItemVariantBase):
    """Schema for creating a new variant"""
    item_id: UUID = None


class ItemVariantUpdate(SQLModel):
    """Partial update for existing variant"""
    size: Optional[str] = None
    color: Optional[str] = None
    status: Optional[ItemVariantStatus] = None
    quantity: Optional[int] = None
    service_start_time: Optional[date] = None
    service_end_time: Optional[date] = None
    prices: Optional[List[ItemVariantPriceBase]] = None
    is_archived: Optional[bool] = None


class ItemVariantPublicInternal(ItemVariantBase):
    id: UUID


class ItemVariantPublic(ItemVariantBase):
    id: UUID
    item_id: UUID


class ItemVariantFilters(SQLModel):
    id: Optional[List[UUID]] = None
    item_id: Optional[List[UUID]] = None
    size: Optional[str] = None
    color: Optional[str] = None
    status: Optional[List[ItemVariantStatus]] = None
    service_start_time: Optional[date] = None
    service_end_time: Optional[date] = None


class ItemVariantQuantity(SQLModel):
    """Used when creating or updating an order with specific variant quantities"""
    item_id: UUID
    item_variant_id: UUID
    quantity: int = Field(default=1, ge=1)
    price: int = Field(default=0, ge=0)
    deposit: int = Field(default=0, ge=0)
