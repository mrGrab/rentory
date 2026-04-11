from datetime import date
from typing import Optional

from sqlmodel import Session, select, func

from models.order import Order
from models.payment import Payment, PaymentMethod, PaymentType
from models.finance import FinanceSummary, PaymentMethodBreakdown


class FinanceService:

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_summary(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> FinanceSummary:
        # ---------- Payments totals ----------
        stmt = select(
            Payment.entry_type,
            Payment.payment_method,
            func.sum(Payment.amount).label("total"),
        ).group_by(Payment.entry_type, Payment.payment_method)

        if date_from or date_to:
            stmt = stmt.join(Order, Payment.order_id == Order.id)
            if date_from:
                stmt = stmt.where(Order.start_time >= date_from)
            if date_to:
                stmt = stmt.where(Order.start_time <= date_to)

        rows = self.session.exec(stmt).all()

        total_rent_received = 0
        total_deposits_received = 0
        by_method = {m.value: 0 for m in PaymentMethod}

        for row in rows:
            entry_type, method, total = row
            total = total or 0
            if entry_type == PaymentType.PAYMENT:
                total_rent_received += total
            else:
                total_deposits_received += total
            by_method[method] = by_method.get(method, 0) + total

        # ---------- Outstanding amounts ----------
        order_stmt = select(
            func.sum(Order.price).label("total_price"),
            func.sum(Order.deposit_amount).label("total_deposit"),
        ).where(Order.is_archived.is_(False))

        if date_from:
            order_stmt = order_stmt.where(Order.start_time >= date_from)
        if date_to:
            order_stmt = order_stmt.where(Order.start_time <= date_to)

        order_totals = self.session.exec(order_stmt).one()
        total_price = order_totals.total_price or 0
        total_deposit = order_totals.total_deposit or 0

        outstanding_rent = max(total_price - total_rent_received, 0)
        outstanding_deposits = max(total_deposit - total_deposits_received, 0)

        return FinanceSummary(
            date_from=date_from,
            date_to=date_to,
            total_rent_received=total_rent_received,
            total_deposits_received=total_deposits_received,
            total_collected=total_rent_received + total_deposits_received,
            outstanding_rent=outstanding_rent,
            outstanding_deposits=outstanding_deposits,
            total_outstanding=outstanding_rent + outstanding_deposits,
            by_method=PaymentMethodBreakdown(
                cash=by_method.get("cash", 0),
                card=by_method.get("card", 0),
                terminal=by_method.get("terminal", 0),
            ),
        )
