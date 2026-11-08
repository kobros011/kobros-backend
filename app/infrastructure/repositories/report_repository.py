from uuid import UUID
from datetime import date
from typing import List, Optional, Sequence, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import Select
from sqlalchemy import func, cast, String

from ..models.payment_model import PaymentModel
from ..models.loan_model import LoanModel
from ..models.client_route_model import ClientRouteModel
from ..models.client_model import ClientModel
from ..models.route_model import RouteModel
from .loan_stats import build_loan_stats
from app.core.clock import today_bogota
from app.core.pagination import PaginationParams, paginate_mappings


class ReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _stmt(
        self,
        route_ids: Optional[Sequence[UUID]],
        brand_id: Optional[UUID],
        text: Optional[str],
        *,
        delinquency: bool,
        today: date,
        currency: Optional[str] = None,
    ) -> Select:
        """Cartera (créditos activos con saldo) o mora (con cuotas vencidas impagas), ambas sobre `loan_stats`
        para que Cartera, Cartera en mora y el Dashboard usen siempre las mismas cifras."""
        stats = build_loan_stats(today)

        columns = [
            ClientModel.id.label("client_id"),
            ClientModel.full_name.label("client_name"),
            LoanModel.id.label("loan_id"),
            LoanModel.loan_number,
            RouteModel.id.label("route_id"),
            RouteModel.name.label("route_name"),
            stats.c.value_total_loan,
            stats.c.paid.label("total_paid"),
            LoanModel.end_date,
        ]
        if delinquency:
            columns += [
                stats.c.overdue_amount.label("balance"),
                stats.c.balance.label("loan_balance"),
                stats.c.overdue_quotas,
                stats.c.overdue_since,
                stats.c.days_overdue,
            ]
        else:
            columns += [stats.c.balance.label("balance"), LoanModel.payment_method]

        stmt = (
            select(*columns)
            .select_from(LoanModel)
            .join(stats, stats.c.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .join(ClientModel, ClientRouteModel.cliente_id == ClientModel.id)
            .join(RouteModel, ClientRouteModel.route_id == RouteModel.id)
            .where(LoanModel.active == True, RouteModel.active == True)  # igual que el dashboard: rutas inactivas no cuentan
        )
        stmt = stmt.where(stats.c.overdue_amount > 0) if delinquency else stmt.where(stats.c.balance > 0)

        if route_ids is not None:
            stmt = stmt.where(RouteModel.id.in_(route_ids))
        if currency:
            stmt = stmt.where(RouteModel.currency == currency)
        if brand_id:
            stmt = stmt.where(ClientModel.brand_id == brand_id)
        if text:
            like = f"%{text.strip()}%"
            stmt = stmt.where(ClientModel.full_name.ilike(like) | cast(LoanModel.loan_number, String).ilike(like))

        if delinquency:
            return stmt.order_by(stats.c.days_overdue.desc(), LoanModel.id)
        return stmt.order_by(stats.c.balance.desc(), LoanModel.id)

    @staticmethod
    def _round_row(row: dict) -> dict:
        row = dict(row)
        for key in ("value_total_loan", "total_paid", "balance", "loan_balance"):
            if key in row and row[key] is not None:
                row[key] = round(float(row[key]), 2)
        return row

    async def list_portfolio(
        self,
        route_ids: Optional[Sequence[UUID]],
        brand_id: Optional[UUID],
        text: Optional[str],
        params: Optional[PaginationParams],
        currency: Optional[str] = None,
    ) -> Tuple[List[dict], int]:
        stmt = self._stmt(route_ids, brand_id, text, delinquency=False, today=today_bogota(), currency=currency)
        rows, total = await paginate_mappings(self.db, stmt, params)
        return [self._round_row(r) for r in rows], total

    async def list_delinquency(
        self,
        route_ids: Optional[Sequence[UUID]],
        brand_id: Optional[UUID],
        text: Optional[str],
        params: Optional[PaginationParams],
        currency: Optional[str] = None,
    ) -> Tuple[List[dict], int]:
        stmt = self._stmt(route_ids, brand_id, text, delinquency=True, today=today_bogota(), currency=currency)
        rows, total = await paginate_mappings(self.db, stmt, params)
        return [self._round_row(r) for r in rows], total

    async def _summary(self, route_ids, brand_id, text, *, delinquency: bool, currency: Optional[str] = None) -> dict:
        stmt = self._stmt(route_ids, brand_id, text, delinquency=delinquency, today=today_bogota(), currency=currency).order_by(None)
        sub = stmt.subquery()
        total_balance, count = (
            await self.db.execute(select(func.coalesce(func.sum(sub.c.balance), 0), func.count()).select_from(sub))
        ).one()
        return {"total_balance": round(float(total_balance), 2), "count": count}

    async def portfolio_summary(self, route_ids: Optional[Sequence[UUID]], brand_id: Optional[UUID], text: Optional[str], currency: Optional[str] = None) -> dict:
        return await self._summary(route_ids, brand_id, text, delinquency=False, currency=currency)

    async def delinquency_summary(self, route_ids: Optional[Sequence[UUID]], brand_id: Optional[UUID], text: Optional[str], currency: Optional[str] = None) -> dict:
        return await self._summary(route_ids, brand_id, text, delinquency=True, currency=currency)

    async def get_client_payment_history(self, client_id: UUID) -> List[dict]:
        stmt = (
            select(
                PaymentModel.id.label("payment_id"),
                LoanModel.id.label("loan_id"),
                LoanModel.loan_number,
                PaymentModel.quota_number,
                PaymentModel.pay_date,
                PaymentModel.payment_date,
                PaymentModel.value,
                PaymentModel.applied,
                PaymentModel.status,
            )
            .select_from(PaymentModel)
            .join(LoanModel, PaymentModel.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(ClientRouteModel.cliente_id == client_id)
            .order_by(PaymentModel.pay_date.desc(), PaymentModel.quota_number.desc())
        )
        rows = (await self.db.execute(stmt)).mappings().all()
        return [dict(row) for row in rows]
