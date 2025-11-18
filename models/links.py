from uuid import UUID
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from models.order import Order
    from models.item_variant import ItemVariant


class OrderItemLink(SQLModel, table=True):
    order_id: int = Field(foreign_key="order.id",
                          primary_key=True,
                          ondelete="CASCADE")
    item_variant_id: UUID = Field(foreign_key="itemvariant.id",
                                  primary_key=True)
    price: int = Field(default=0, ge=0)
    deposit: int = Field(default=0, ge=0)
    quantity: int = Field(default=1, ge=1)
    order: Optional["Order"] = Relationship(back_populates="item_links")
    item_variant: Optional["ItemVariant"] = Relationship(
        back_populates="order_links")
