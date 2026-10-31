from uuid import UUID
from datetime import date as date_type
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from ..models.payment_model import PaymentModel
from ..models.loan_model import LoanModel
from ..models.client_route_model import ClientRouteModel
from ..models.client_model import ClientModel
from ..models.route_model import RouteModel


class ReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_portfolio(
        self,
        route_id: Optional[UUID] = None,
        brand_id: Optional[UUID] = None,
    ) -> List[dict]:
        paid_sub = (
            select(
                PaymentModel.loan_id,
                func.coalesce(func.sum(PaymentModel.applied), 0).label("total_paid"),
            )
            .where(PaymentModel.status == "PAGADO")
            .group_by(PaymentModel.loan_id)
            .subquery()
        )

        stmt = (
            select(
                ClientModel.id.label("client_id"),
                ClientModel.full_name.label("client_name"),
                LoanModel.id.label("loan_id"),
                LoanModel.loan_number,
                RouteModel.id.label("route_id"),
                RouteModel.name.label("route_name"),
                LoanModel.value_total_loan,
                func.coalesce(paid_sub.c.total_paid, 0).label("total_paid"),
                LoanModel.end_date,
                LoanModel.payment_method,
            )
            .select_from(LoanModel)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .join(ClientModel, ClientRouteModel.cliente_id == ClientModel.id)
            .join(RouteModel, ClientRouteModel.route_id == RouteModel.id)
            .outerjoin(paid_sub, paid_sub.c.loan_id == LoanModel.id)
            .where(LoanModel.active == True)
        )

        if route_id:
            stmt = stmt.where(RouteModel.id == route_id)
        if brand_id:
            stmt = stmt.where(ClientModel.brand_id == brand_id)

        result = await self.db.execute(stmt)
        rows = result.mappings().all()

        items = []
        for r in rows:
            balance = float(r["value_total_loan"]) - float(r["total_paid"])
            if balance <= 0:
                continue
            items.append({
                "client_id": r["client_id"],
                "client_name": r["client_name"],
                "loan_id": r["loan_id"],
                "loan_number": r["loan_number"],
                "route_id": r["route_id"],
                "route_name": r["route_name"],
                "value_total_loan": float(r["value_total_loan"]),
                "total_paid": float(r["total_paid"]),
                "balance": round(balance, 2),
                "end_date": r["end_date"],
                "payment_method": r["payment_method"],
            })
        return items

    async def get_delinquency(
        self,
        route_id: Optional[UUID] = None,
        brand_id: Optional[UUID] = None,
    ) -> List[dict]:
        today = date_type.today()

        paid_sub = (
            select(
                PaymentModel.loan_id,
                func.coalesce(func.sum(PaymentModel.applied), 0).label("total_paid"),
            )
            .where(PaymentModel.status == "PAGADO")
            .group_by(PaymentModel.loan_id)
            .subquery()
        )

        stmt = (
            select(
                ClientModel.id.label("client_id"),
                ClientModel.full_name.label("client_name"),
                LoanModel.id.label("loan_id"),
                LoanModel.loan_number,
                RouteModel.id.label("route_id"),
                RouteModel.name.label("route_name"),
                LoanModel.value_total_loan,
                func.coalesce(paid_sub.c.total_paid, 0).label("total_paid"),
                LoanModel.end_date,
            )
            .select_from(LoanModel)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .join(ClientModel, ClientRouteModel.cliente_id == ClientModel.id)
            .join(RouteModel, ClientRouteModel.route_id == RouteModel.id)
            .outerjoin(paid_sub, paid_sub.c.loan_id == LoanModel.id)
            .where(LoanModel.active == True)
            .where(LoanModel.end_date < today)
        )

        if route_id:
            stmt = stmt.where(RouteModel.id == route_id)
        if brand_id:
            stmt = stmt.where(ClientModel.brand_id == brand_id)

        result = await self.db.execute(stmt)
        rows = result.mappings().all()

        items = []
        for r in rows:
            balance = float(r["value_total_loan"]) - float(r["total_paid"])
            if balance <= 0:
                continue
            days_overdue = (today - r["end_date"]).days
            items.append({
                "client_id": r["client_id"],
                "client_name": r["client_name"],
                "loan_id": r["loan_id"],
                "loan_number": r["loan_number"],
                "route_id": r["route_id"],
                "route_name": r["route_name"],
                "value_total_loan": float(r["value_total_loan"]),
                "total_paid": float(r["total_paid"]),
                "balance": round(balance, 2),
                "end_date": r["end_date"],
                "days_overdue": days_overdue,
            })
        return items

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
            .order_by(PaymentModel.pay_date.asc(), LoanModel.loan_number.asc(), PaymentModel.quota_number.asc())
        )

        result = await self.db.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "payment_id": r["payment_id"],
                "loan_id": r["loan_id"],
                "loan_number": r["loan_number"],
                "quota_number": r["quota_number"],
                "pay_date": r["pay_date"],
                "payment_date": r["payment_date"],
                "value": float(r["value"]),
                "applied": float(r["applied"]),
                "status": r["status"],
            }
            for r in rows
        ]
