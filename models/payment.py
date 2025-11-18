from uuid import UUID
from enum import Enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

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
    note: Optional[str] = Field(default=None, max_length=512)
    order_id: int = Field(foreign_key="order.id", index=True)

    order: Optional["Order"] = Relationship(back_populates="payments")


# ---------- API Schemas ----------


class PaymentBase(SQLModel):
    id: Optional[UUID] = None
    amount: int = Field(ge=0)
    payment_method: PaymentMethod
    entry_type: PaymentType
    note: Optional[str] = None


class PaymentPublic(PaymentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
