from uuid import UUID
from enum import Enum
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship, Column, JSON

from models.common import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from models.item_variant import (ItemVariant, ItemVariantUpdate,
                                     ItemVariantBase,
                                     ItemVariantPublicInternal,
                                     ItemVariantStatus)

# ---------- ENUMS ----------


class ItemStatus(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"


# ---------- Database Model ----------


class Item(UUIDMixin, TimestampMixin, table=True):
    title: str = Field(index=True, unique=True, max_length=255)
    category: Optional[str] = Field(default=None, index=True, max_length=100)
    description: Optional[str] = Field(default=None, max_length=512)
    image_url: Optional[str] = Field(default=None, max_length=512)
    status: ItemStatus = Field(default=ItemStatus.IN_STOCK, index=True)
    is_archived: bool = Field(default=False, index=True)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    variants: List["ItemVariant"] = Relationship(back_populates="item",
                                                 cascade_delete=True)


# ---------- API Schemas ----------


class ItemBase(SQLModel):
    title: str = Field(max_length=255)
    category: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=512)
    image_url: Optional[str] = Field(default=None, max_length=512)
    status: ItemStatus = ItemStatus.IN_STOCK
    tags: List[str] = Field(default_factory=list)


class ItemCreate(ItemBase):
    """Used when creating a new item"""
    variants: Optional[List["ItemVariantBase"]] = Field(default_factory=list)


class ItemUpdate(SQLModel):
    """Partial update for existing item"""
    title: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=512)
    image_url: Optional[str] = Field(default=None, max_length=512)
    status: Optional[ItemStatus] = None
    tags: Optional[List[str]] = None
    variants: Optional[List["ItemVariantUpdate"]] = Field(default_factory=list)
    is_archived: Optional[bool] = None


class ItemPublic(ItemBase):
    id: UUID
    variants: List["ItemVariantPublicInternal"] = Field(default_factory=list)
    order_ids: List[int] = Field(default_factory=list)


class ItemFilters(SQLModel):
    id: Optional[List[UUID]] = None
    title: Optional[str] = None
    category: Optional[str] = None
    status: Optional[ItemStatus] = None
    size: Optional[str] = None
    color: Optional[str] = None
    variant_status: Optional["ItemVariantStatus"] = None
    tag: Optional[str] = None
    q: Optional[str] = None
