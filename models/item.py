from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from models.common import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from models.item_variant import (
        ItemVariant,
        ItemVariantBase,
        ItemVariantPublicInternal,
        ItemVariantStatus,
        ItemVariantUpdate,
    )

# ---------- ENUMS ----------


class ItemStatus(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"


# ---------- Database Model ----------


class Item(UUIDMixin, TimestampMixin, table=True):
    title: str = Field(index=True, unique=True, max_length=255)
    category: str | None = Field(default=None, index=True, max_length=100)
    description: str | None = Field(default=None, max_length=512)
    image_url: str | None = Field(default=None, max_length=512)
    status: ItemStatus = Field(default=ItemStatus.IN_STOCK, index=True)
    is_archived: bool = Field(default=False, index=True)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    variants: list[ItemVariant] = Relationship(
        back_populates="item", cascade_delete=True
    )


# ---------- API Schemas ----------


class ItemBase(SQLModel):
    title: str = Field(max_length=255)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=512)
    image_url: str | None = Field(default=None, max_length=512)
    status: ItemStatus = ItemStatus.IN_STOCK
    tags: list[str] = Field(default_factory=list)


class ItemCreate(ItemBase):
    """Used when creating a new item"""

    variants: list[ItemVariantBase] | None = Field(default_factory=list)


class ItemUpdate(SQLModel):
    """Partial update for existing item"""

    title: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=512)
    image_url: str | None = Field(default=None, max_length=512)
    status: ItemStatus | None = None
    tags: list[str] | None = None
    variants: list[ItemVariantUpdate] | None = Field(default_factory=list)
    is_archived: bool | None = None


class ItemPublic(ItemBase):
    id: UUID
    variants: list[ItemVariantPublicInternal] = Field(default_factory=list)
    order_ids: list[int] = Field(default_factory=list)


class ItemFilters(SQLModel):
    id: list[UUID] | None = None
    title: str | None = None
    category: str | None = None
    status: ItemStatus | None = None
    size: str | None = None
    color: str | None = None
    variant_status: ItemVariantStatus | None = None
    tag: str | None = None
    q: str | None = None
    is_archived: bool | None = None
