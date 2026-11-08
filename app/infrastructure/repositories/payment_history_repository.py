"""Historial de cuotas de un crédito (estado, saldo, mora y quién recaudó), calculado en SQL.

Definiciones (hoy = fecha Bogotá, ver `app.core.clock`; misma tolerancia que `loan_stats`):
* pagada     = applied >= value - 0.01
* mora       = no pagada y pay_date < hoy
* pendiente  = no pagada y pay_date >= hoy
* saldo      = max(value - applied, 0)
* can_pay    = no pagada y pay_date <= hoy (vence hoy o ya venció)
"""
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, Integer, and_, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.exceptions import NotFoundException
from ...core.pagination import PaginationParams, paginate_mappings
from ..models.client_model import ClientRouteModel
from ..models.loan_model import LoanModel
from ..models.payment_model import PaymentModel
from ..models.route_model import RouteModel
from ..models.user_model import UserModel
from .loan_stats import UNPAID_TOLERANCE

STATUSES = ("pagado", "pendiente", "mora")


class PaymentHistoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _expressions(today: date) -> dict:
        applied = func.coalesce(PaymentModel.applied, 0)
        value = func.coalesce(PaymentModel.value, 0)
        paid = applied >= value - UNPAID_TOLERANCE
        overdue = and_(~paid, PaymentModel.pay_date < today)
        today_date = literal(today, Date)
        return {
            "applied": applied,
            "value": value,
            "paid": paid,
            "overdue": overdue,
            "status": case((paid, "pagado"), (overdue, "mora"), else_="pendiente"),
            "balance": func.greatest(value - applied, 0),
            "days_overdue": case((overdue, (today_date - PaymentModel.pay_date).cast(Integer)), else_=0),
            "paid_late_days": case(
                (and_(paid, PaymentModel.payment_date.isnot(None)),
                 func.greatest((PaymentModel.payment_date - PaymentModel.pay_date).cast(Integer), 0)),
                else_=0,
            ),
            "can_pay": and_(~paid, PaymentModel.pay_date <= today),
        }

    async def _ensure_visible(self, loan_id: UUID, brand_id: Optional[UUID]) -> None:
        """404 si el crédito no existe o es de otra marca (brand_id None = sin restricción, solo dev)."""
        stmt = (
            select(LoanModel.id)
            .join(ClientRouteModel, ClientRouteModel.id == LoanModel.clientroute_id)
            .join(RouteModel, RouteModel.id == ClientRouteModel.route_id)
            .where(LoanModel.id == loan_id)
        )
        if brand_id is not None:
            stmt = stmt.where(RouteModel.brand_id == brand_id)
        if (await self.db.execute(stmt)).first() is None:
            raise NotFoundException("El crédito no fue encontrado")

    async def history(
        self,
        loan_id: UUID,
        brand_id: Optional[UUID],
        today: date,
        status: Optional[str],
        params: PaginationParams,
    ) -> tuple[list[dict], int, dict]:
        await self._ensure_visible(loan_id, brand_id)
        e = self._expressions(today)

        stmt = (
            select(
                PaymentModel.id,
                PaymentModel.quota_number,
                PaymentModel.pay_date,
                PaymentModel.payment_date,
                e["value"].label("value"),
                e["applied"].label("applied"),
                e["balance"].label("balance"),
                e["status"].label("status"),
                e["days_overdue"].label("days_overdue"),
                e["paid_late_days"].label("paid_late_days"),
                UserModel.id.label("collected_by_id"),
                UserModel.full_name.label("collected_by_name"),
                e["can_pay"].label("can_pay"),
            )
            .outerjoin(UserModel, UserModel.id == PaymentModel.collected_by)
            .where(PaymentModel.loan_id == loan_id, PaymentModel.active.is_(True))
            .order_by(PaymentModel.quota_number)
        )
        if status in STATUSES:
            stmt = stmt.where(e["status"] == status)
        items, total = await paginate_mappings(self.db, stmt, params)

        agg = (await self.db.execute(
            select(
                func.count().label("total_quotas"),
                func.count().filter(e["paid"]).label("paid"),
                func.count().filter(~e["paid"] & ~e["overdue"]).label("pending"),
                func.count().filter(e["overdue"]).label("overdue"),
                func.coalesce(func.sum(e["value"]), 0).label("total_due"),
                func.coalesce(func.sum(e["applied"]), 0).label("total_paid"),
                func.coalesce(func.sum(e["balance"]), 0).label("total_balance"),
            ).where(PaymentModel.loan_id == loan_id, PaymentModel.active.is_(True))
        )).mappings().one()

        due, paid = float(agg["total_due"]), float(agg["total_paid"])
        summary = {
            "total_quotas": agg["total_quotas"],
            "paid": agg["paid"],
            "pending": agg["pending"],
            "overdue": agg["overdue"],
            "total_due": round(due, 2),
            "total_paid": round(paid, 2),
            "total_balance": round(float(agg["total_balance"]), 2),
            "paid_percent": round(min(100.0, paid / due * 100), 1) if due else 0.0,
        }
        return items, total, summary
