from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import UniqueConstraint, event
from sqlmodel import Field, Relationship, SQLModel

from models.common import TimestampMixin, UUIDMixin

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
    price_type: str | None = Field(default=None, max_length=100)

    variant_id: UUID = Field(foreign_key="itemvariant.id", index=True)
    # Quoted Optional (not X | None) required for SQLAlchemy relationship resolution
    variant: Optional["ItemVariant"] = Relationship(back_populates="prices")  # noqa: UP037, UP045


class ItemVariant(UUIDMixin, TimestampMixin, SQLModel, table=True):
    """Represents a specific variant of an item (e.g., size M, color Red)"""

    __table_args__ = (
        UniqueConstraint(
            "item_id",
            "size_key",
            "color_key",
            "active_identity_key",
            name="uq_active_item_variant_identity",
        ),
    )

    quantity: int = Field(default=1, ge=0)
    quantity_in_maintenance: int = Field(
        default=0, ge=0, sa_column_kwargs={"server_default": "0"}
    )
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    image_url: str | None = Field(default=None, max_length=512)
    service_start_time: date | None = None
    service_end_time: date | None = None
    is_archived: bool = Field(default=False, index=True)
    size_key: str = Field(default="", max_length=50)
    color_key: str = Field(default="", max_length=50)
    active_identity_key: str | None = Field(default=None, max_length=64)
    status: ItemVariantStatus = Field(default=ItemVariantStatus.AVAILABLE, index=True)

    item_id: UUID = Field(foreign_key="item.id", index=True)
    # Quoted Optional (not X | None) required for SQLAlchemy relationship resolution
    item: Optional["Item"] = Relationship(back_populates="variants")  # noqa: UP037, UP045
    prices: list[ItemVariantPrice] = Relationship(
        back_populates="variant", cascade_delete=True
    )
    order_links: list[OrderItemLink] = Relationship(back_populates="item_variant")

    @staticmethod
    def _normalize_identity(value: str | None) -> str:
        return value.strip().casefold() if value and value.strip() else ""


# ---------- Database Model ----------


class ItemVariantPriceBase(SQLModel):
    id: UUID | None = None
    amount: int
    deposit: int | None = Field(default=0, ge=0)
    price_type: str | None = None


class ItemVariantBase(SQLModel):
    """Base schema for item variants"""

    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    image_url: str | None = Field(default=None, max_length=512)
    status: ItemVariantStatus = Field(default=ItemVariantStatus.AVAILABLE)
    quantity: int = Field(default=1, ge=0)
    quantity_in_maintenance: int = Field(default=0, ge=0)
    service_start_time: date | None = None
    service_end_time: date | None = None
    prices: list[ItemVariantPriceBase] = Field(default_factory=list)


class ItemVariantCreate(ItemVariantBase):
    """Schema for creating a new variant"""

    item_id: UUID


class ItemVariantUpdate(SQLModel):
    """Partial update for existing variant"""

    id: UUID | None = None
    size: str | None = None
    color: str | None = None
    image_url: str | None = Field(default=None, max_length=512)
    status: ItemVariantStatus | None = None
    quantity: int | None = None
    quantity_in_maintenance: int | None = None
    service_start_time: date | None = None
    service_end_time: date | None = None
    prices: list[ItemVariantPriceBase] | None = None
    is_archived: bool | None = None


class ItemVariantPublicInternal(ItemVariantBase):
    id: UUID
    # Only populated by the availability-check endpoint; None otherwise
    available_quantity: int | None = None


class ItemVariantPublic(ItemVariantBase):
    id: UUID
    item_id: UUID
    # Only populated by the availability-check endpoint; None otherwise
    available_quantity: int | None = None


class ItemVariantFilters(SQLModel):
    id: list[UUID] | None = None
    item_id: list[UUID] | None = None
    size: str | None = None
    color: str | None = None
    status: list[ItemVariantStatus] | None = None
    service_start_time: date | None = None
    service_end_time: date | None = None
    is_archived: bool | None = None


class ItemVariantQuantity(SQLModel):
    """Used when creating or updating an order with specific variant quantities"""

    item_id: UUID
    item_variant_id: UUID
    quantity: int = Field(default=1, ge=1)
    price: int = Field(default=0, ge=0)
    deposit: int = Field(default=0, ge=0)
    item_variant_price_id: UUID | None = None


@event.listens_for(ItemVariant, "before_insert")
@event.listens_for(ItemVariant, "before_update")
def set_variant_identity_keys(_, __, variant: ItemVariant) -> None:
    variant.size_key = ItemVariant._normalize_identity(variant.size)
    variant.color_key = ItemVariant._normalize_identity(variant.color)
    variant.active_identity_key = None if variant.is_archived else "active"
