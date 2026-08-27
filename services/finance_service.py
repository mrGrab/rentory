from datetime import date

from sqlalchemy import distinct
from sqlmodel import Session, func, select

from models.finance import (
    FinanceSummary,
    PaymentMethodBreakdown,
    PaymentRecord,
    UserBreakdown,
)
from models.order import Order, OrderStatus
from models.payment import Payment, PaymentMethod, PaymentType
from models.user import User


class FinanceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _apply_date_filter(self, stmt, date_from: date | None, date_to: date | None):
        stmt = stmt.where(Order.is_archived.is_(False))
        if date_from:
            stmt = stmt.where(Order.start_time >= date_from)
        if date_to:
            stmt = stmt.where(Order.start_time <= date_to)
        return stmt

    def _get_payment_totals(self, date_from, date_to):
        stmt = self._apply_date_filter(
            select(
                Payment.entry_type,
                Payment.payment_method,
                func.sum(Payment.amount).label("total"),
            )
            .join(Order, Payment.order_id == Order.id)
            .group_by(Payment.entry_type, Payment.payment_method),
            date_from,
            date_to,
        )
        rows = self.session.exec(stmt).all()

        total_rent = 0
        total_deposits = 0
        by_method = {m.value: 0 for m in PaymentMethod}

        for entry_type, method, total in rows:
            total = total or 0
            if entry_type == PaymentType.PAYMENT:
                total_rent += total
            else:
                total_deposits += total
            by_method[method] = by_method.get(method, 0) + total

        return total_rent, total_deposits, by_method

    def _get_order_stats(self, date_from, date_to):
        stmt = self._apply_date_filter(
            select(
                func.count(Order.id).label("cnt"),
                func.avg(Order.price).label("avg_price"),
            ),
            date_from,
            date_to,
        )
        row = self.session.exec(stmt).one()
        return row.cnt or 0, int(row.avg_price or 0)

    def _get_returned_stats(self, date_from, date_to):
        stmt = self._apply_date_filter(
            select(
                func.count(Order.id).label("cnt"),
                func.sum(Order.deposit_amount).label("deposit_sum"),
            ).where(Order.status == OrderStatus.RETURNED),
            date_from,
            date_to,
        )
        row = self.session.exec(stmt).one()
        return row.cnt or 0, row.deposit_sum or 0

    def _get_by_user(self, date_from, date_to) -> list[UserBreakdown]:
        stmt = self._apply_date_filter(
            select(
                User.id.label("user_id"),
                User.username,
                func.sum(Payment.amount).label("total_income"),
                func.count(distinct(Order.id)).label("order_count"),
            )
            .join(Order, Payment.order_id == Order.id)
            .join(User, Order.created_by_user_id == User.id)
            .where(Payment.entry_type == PaymentType.PAYMENT)
            .group_by(User.id, User.username),
            date_from,
            date_to,
        )
        return [
            UserBreakdown(
                user_id=str(row.user_id),
                username=row.username,
                total_income=row.total_income or 0,
                order_count=row.order_count or 0,
            )
            for row in self.session.exec(stmt).all()
        ]

    def _get_payment_records(self, date_from, date_to) -> list[PaymentRecord]:
        stmt = self._apply_date_filter(
            select(
                Order.start_time.label("date"),
                Order.id.label("order_id"),
                Payment.amount,
                Payment.entry_type,
                Payment.payment_method,
                User.username,
            )
            .join(Order, Payment.order_id == Order.id)
            .join(User, Order.created_by_user_id == User.id)
            .order_by(Order.start_time.desc()),
            date_from,
            date_to,
        )
        return [
            PaymentRecord(
                date=row.date,
                order_id=row.order_id,
                amount=row.amount,
                entry_type=row.entry_type,
                payment_method=row.payment_method,
                username=row.username,
            )
            for row in self.session.exec(stmt).all()
        ]

    def get_summary(
        self, date_from: date | None = None, date_to: date | None = None
    ) -> FinanceSummary:
        total_rent, total_deposits, by_method = self._get_payment_totals(
            date_from, date_to
        )
        order_count, average_check = self._get_order_stats(date_from, date_to)
        returned_count, deposit_returned = self._get_returned_stats(date_from, date_to)

        return FinanceSummary(
            date_from=date_from,
            date_to=date_to,
            total_rent_received=total_rent,
            total_deposits_received=total_deposits,
            total_collected=total_rent + total_deposits,
            order_count=order_count,
            average_check=average_check,
            returned_order_count=returned_count,
            total_deposit_returned=deposit_returned,
            by_method=PaymentMethodBreakdown(
                cash=by_method.get("cash", 0),
                card=by_method.get("card", 0),
                terminal=by_method.get("terminal", 0),
            ),
            by_user=self._get_by_user(date_from, date_to),
            payments=self._get_payment_records(date_from, date_to),
        )
