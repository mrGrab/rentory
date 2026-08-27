from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from models.common import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from models.order import Order

# ---------- ENUMS ----------


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    TERMINAL = "terminal"


class PaymentType(str, Enum):
    PAYMENT = "payment"
    DEPOSIT = "deposit"


# ---------- Database Model ----------


class Payment(TimestampMixin, UUIDMixin, SQLModel, table=True):
    amount: int = Field(ge=0)
    payment_method: PaymentMethod = Field(max_length=20)
    entry_type: PaymentType = Field(max_length=20)
    note: str | None = Field(default=None, max_length=512)
    order_id: int = Field(foreign_key="order.id", index=True)
    # Quoted Optional (not X | None) required for SQLAlchemy relationship resolution
    order: Optional["Order"] = Relationship(back_populates="payments")  # noqa: UP037, UP045


# ---------- API Schemas ----------


class PaymentBase(SQLModel):
    id: UUID | None = None
    amount: int = Field(ge=0)
    payment_method: PaymentMethod
    entry_type: PaymentType
    note: str | None = None


class PaymentPublic(PaymentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
