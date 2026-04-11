from datetime import date
from typing import Optional
from sqlmodel import SQLModel


class PaymentMethodBreakdown(SQLModel):
    cash: int = 0
    card: int = 0
    terminal: int = 0


class FinanceSummary(SQLModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    total_rent_received: int = 0
    total_deposits_received: int = 0
    total_collected: int = 0
    outstanding_rent: int = 0
    outstanding_deposits: int = 0
    total_outstanding: int = 0
    by_method: PaymentMethodBreakdown = PaymentMethodBreakdown()
