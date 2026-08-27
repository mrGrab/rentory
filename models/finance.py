from datetime import date

from sqlmodel import Field, SQLModel


class PaymentMethodBreakdown(SQLModel):
    cash: int = 0
    card: int = 0
    terminal: int = 0


class UserBreakdown(SQLModel):
    user_id: str
    username: str
    total_income: int = 0
    order_count: int = 0


class PaymentRecord(SQLModel):
    date: date
    order_id: int
    amount: int
    entry_type: str
    payment_method: str
    username: str


class FinanceSummary(SQLModel):
    date_from: date | None = None
    date_to: date | None = None
    total_rent_received: int = 0
    total_deposits_received: int = 0
    total_collected: int = 0
    order_count: int = 0
    average_check: int = 0
    returned_order_count: int = 0
    total_deposit_returned: int = 0
    by_method: PaymentMethodBreakdown = Field(default_factory=PaymentMethodBreakdown)
    by_user: list[UserBreakdown] = Field(default_factory=list)
    payments: list[PaymentRecord] = Field(default_factory=list)
