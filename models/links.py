from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.item_variant import ItemVariant
    from models.order import Order


class OrderItemLink(SQLModel, table=True):
    order_id: int | None = Field(
        default=None, foreign_key="order.id", primary_key=True, ondelete="CASCADE"
    )
    item_variant_id: UUID = Field(foreign_key="itemvariant.id", primary_key=True)
    price: int = Field(default=0, ge=0)
    deposit: int = Field(default=0, ge=0)
    quantity: int = Field(default=1, ge=1)
    item_title_snapshot: str | None = Field(default=None, max_length=255)
    variant_size_snapshot: str | None = Field(default=None, max_length=50)
    variant_color_snapshot: str | None = Field(default=None, max_length=50)
    price_type_snapshot: str | None = Field(default=None, max_length=100)
    # Quoted Optional (not X | None) required for SQLAlchemy relationship resolution
    order: Optional["Order"] = Relationship(back_populates="item_links")  # noqa: UP037, UP045
    item_variant: Optional["ItemVariant"] = Relationship(back_populates="order_links")  # noqa: UP037, UP045
