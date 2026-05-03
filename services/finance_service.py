from datetime import date
from typing import Optional, List

from sqlalchemy import distinct
from sqlmodel import Session, select, func

from models.order import Order, OrderStatus
from models.payment import Payment, PaymentMethod, PaymentType
from models.user import User
from models.finance import (
    FinanceSummary,
    PaymentMethodBreakdown,
    UserBreakdown,
    PaymentRecord,
)


class FinanceService:

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_summary(self,
                    date_from: Optional[date] = None,
                    date_to: Optional[date] = None) -> FinanceSummary:
        # ---------- Payments totals ----------
        stmt = (select(
            Payment.entry_type,
            Payment.payment_method,
            func.sum(Payment.amount).label("total"),
        ).join(Order,
               Payment.order_id == Order.id).group_by(Payment.entry_type,
                                                      Payment.payment_method))

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

        # ---------- Order count & average check ----------
        order_stats_stmt = select(
            func.count(Order.id).label("cnt"),
            func.avg(Order.price).label("avg_price"),
        ).where(Order.is_archived.is_(False))

        if date_from:
            order_stats_stmt = order_stats_stmt.where(
                Order.start_time >= date_from)
        if date_to:
            order_stats_stmt = order_stats_stmt.where(
                Order.start_time <= date_to)

        order_stats = self.session.exec(order_stats_stmt).one()
        order_count = order_stats.cnt or 0
        average_check = int(order_stats.avg_price or 0)

        # ---------- Returned orders ----------
        returned_stmt = select(
            func.count(Order.id).label("cnt"),
            func.sum(Order.deposit_amount).label("deposit_sum"),
        ).where(Order.status == OrderStatus.RETURNED)

        if date_from:
            returned_stmt = returned_stmt.where(Order.start_time >= date_from)
        if date_to:
            returned_stmt = returned_stmt.where(Order.start_time <= date_to)

        returned_row = self.session.exec(returned_stmt).one()
        returned_order_count = returned_row.cnt or 0
        total_deposit_returned = returned_row.deposit_sum or 0

        # ---------- By worker ----------
        by_user_stmt = (select(
            User.id.label("user_id"),
            User.username,
            func.sum(Payment.amount).label("total_income"),
            func.count(distinct(Order.id)).label("order_count"),
        ).join(Order, Payment.order_id == Order.id).join(
            User, Order.created_by_user_id == User.id).where(
                Payment.entry_type == PaymentType.PAYMENT).group_by(
                    User.id, User.username))

        if date_from:
            by_user_stmt = by_user_stmt.where(Order.start_time >= date_from)
        if date_to:
            by_user_stmt = by_user_stmt.where(Order.start_time <= date_to)

        by_user_rows = self.session.exec(by_user_stmt).all()
        by_user: List[UserBreakdown] = [
            UserBreakdown(
                user_id=str(row.user_id),
                username=row.username,
                total_income=row.total_income or 0,
                order_count=row.order_count or 0,
            ) for row in by_user_rows
        ]

        # ---------- Transaction records (date, sum, type, who) ----------
        payments_stmt = (select(
            Order.start_time.label("date"),
            Order.id.label("order_id"),
            Payment.amount,
            Payment.entry_type,
            Payment.payment_method,
            User.username,
        ).join(Order, Payment.order_id == Order.id).join(
            User, Order.created_by_user_id == User.id).order_by(
                Order.start_time.desc()))

        if date_from:
            payments_stmt = payments_stmt.where(Order.start_time >= date_from)
        if date_to:
            payments_stmt = payments_stmt.where(Order.start_time <= date_to)

        payment_rows = self.session.exec(payments_stmt).all()
        payments: List[PaymentRecord] = [
            PaymentRecord(
                date=row.date,
                order_id=row.order_id,
                amount=row.amount,
                entry_type=row.entry_type,
                payment_method=row.payment_method,
                username=row.username,
            ) for row in payment_rows
        ]

        return FinanceSummary(
            date_from=date_from,
            date_to=date_to,
            total_rent_received=total_rent_received,
            total_deposits_received=total_deposits_received,
            total_collected=total_rent_received + total_deposits_received,
            order_count=order_count,
            average_check=average_check,
            returned_order_count=returned_order_count,
            total_deposit_returned=total_deposit_returned,
            by_method=PaymentMethodBreakdown(
                cash=by_method.get("cash", 0),
                card=by_method.get("card", 0),
                terminal=by_method.get("terminal", 0),
            ),
            by_user=by_user,
            payments=payments,
        )
