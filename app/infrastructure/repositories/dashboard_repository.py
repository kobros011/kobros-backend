from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.pagination import PaginationParams, paginate_mappings

from ..models.client_model import ClientModel
from ..models.client_route_model import ClientRouteModel
from ..models.expense_model import ExpenseModel
from ..models.loan_model import LoanModel
from ..models.models import UserType
from ..models.payment_model import PaymentModel
from ..models.route_model import RouteModel
from ..models.user_model import UserModel
from .loan_stats import CRITICAL_DAYS, build_loan_stats


@dataclass
class Scope:
    """Rutas y recaudadores que el usuario puede ver, ya filtrados por marca/rol y por los filtros del dashboard."""

    # Alcance completo del usuario (alimenta los selectores, sin aplicar route_id/collector_id).
    all_routes: List[dict] = field(default_factory=list)
    all_collectors: List[dict] = field(default_factory=list)
    # Alcance con los filtros aplicados (alimenta todas las cifras).
    routes: List[dict] = field(default_factory=list)
    collector_id: Optional[UUID] = None

    @property
    def route_ids(self) -> List[UUID]:
        return [route["id"] for route in self.routes]

    def collectors_of(self, route: dict) -> List[dict]:
        """Recaudadores de una ruta, respetando el filtro de recaudador (como el mock)."""
        return [
            collector for collector in self.all_collectors
            if collector["id"] in route["collector_ids"] and (not self.collector_id or collector["id"] == self.collector_id)
        ]


class DashboardRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- alcance ---------------------------------------------------------------
    async def resolve_scope(
        self,
        user: UserModel,
        brand_id: Optional[UUID],
        route_id: Optional[UUID],
        collector_id: Optional[UUID],
    ) -> Scope:
        """Rutas activas de la marca; el socio (04) solo las suyas. `route_id`/`collector_id` fuera del alcance → 404."""
        routes_stmt = select(RouteModel).where(RouteModel.active == True).order_by(RouteModel.name, RouteModel.id)
        collectors_stmt = (
            select(UserModel)
            .where(UserModel.type_user == UserType.collector, UserModel.active == True)
            .order_by(UserModel.full_name, UserModel.id)
        )
        if brand_id:
            routes_stmt = routes_stmt.where(RouteModel.brand_id == brand_id)
            collectors_stmt = collectors_stmt.where(UserModel.brand_id == brand_id)
        if user.type_user == UserType.partner:
            routes_stmt = routes_stmt.where(RouteModel.allowed_users_ids.contains([user.id]))

        route_models = (await self.db.execute(routes_stmt)).scalars().all()
        collector_models = (await self.db.execute(collectors_stmt)).scalars().all()
        collector_by_id = {c.id: c for c in collector_models}

        all_routes = [
            {
                "id": route.id,
                "name": route.name,
                "collector_ids": [uid for uid in (route.allowed_users_ids or []) if uid in collector_by_id],
            }
            for route in route_models
        ]
        assigned = {uid for route in all_routes for uid in route["collector_ids"]}
        all_collectors = [
            {"id": c.id, "full_name": c.full_name or c.username}
            for c in collector_models if c.id in assigned
        ]

        routes = all_routes
        if collector_id:
            if collector_id not in {c["id"] for c in all_collectors}:
                raise NotFoundException("El recaudador no fue encontrado")
            routes = [route for route in routes if collector_id in route["collector_ids"]]
        if route_id:
            routes = [route for route in routes if route["id"] == route_id]
            if not routes:
                raise NotFoundException("La ruta no fue encontrada")

        return Scope(all_routes=all_routes, all_collectors=all_collectors, routes=routes, collector_id=collector_id)

    # ---- resumen ---------------------------------------------------------------
    async def summary(self, scope: Scope, today: date, days: int) -> dict:
        route_ids = scope.route_ids
        by_route_rows = await self._route_totals(route_ids, today)
        clients_active, clients_inactive = await self._client_counts(route_ids)
        critical_clients = await self._critical_clients(route_ids, today)
        daily = await self._daily(route_ids, today, days)

        by_route = []
        for route in scope.routes:
            totals = by_route_rows.get(route["id"], _EMPTY_TOTALS)
            by_route.append({
                "route_id": route["id"],
                "route_name": route["name"],
                "collector_names": [c["full_name"] for c in scope.collectors_of(route)],
                "active": totals["active"],
                "late": totals["late"],
                "rate": _pct(totals["late"], totals["active"]),
            })
        by_route.sort(key=lambda row: row["active"], reverse=True)

        collector_rows = []
        for collector in scope.all_collectors:
            if scope.collector_id and collector["id"] != scope.collector_id:
                continue
            assigned = [route for route in scope.routes if collector["id"] in route["collector_ids"]]
            if not assigned:
                continue
            goal = sum(by_route_rows.get(route["id"], _EMPTY_TOTALS)["lent"] for route in assigned)
            collected = sum(by_route_rows.get(route["id"], _EMPTY_TOTALS)["paid"] for route in assigned)
            collector_rows.append({
                "collector_id": collector["id"],
                "full_name": collector["full_name"],
                "route_names": [route["name"] for route in assigned],
                "goal": _money(goal),
                "collected": _money(collected),
                "percent": _pct(collected, goal),
            })
        collector_rows.sort(key=lambda row: row["percent"], reverse=True)

        totals = {key: sum(row[key] for row in by_route_rows.values()) for key in _EMPTY_TOTALS}
        portfolio_total, late_total = totals["active"], totals["late"]
        clients_total = clients_active + clients_inactive
        in_field = {uid for route in scope.routes for uid in (c["id"] for c in scope.collectors_of(route))}

        return {
            "kpis": {
                "portfolio_total": _money(portfolio_total),
                "portfolio_loans": int(totals["loans"]),
                "delinquency_total": _money(late_total),
                "delinquency_loans": int(totals["late_loans"]),
                "delinquency_rate": _pct(late_total, portfolio_total),
                "total_lent": _money(totals["lent"]),
                "total_paid": _money(totals["paid"]),
                "effectiveness": min(100.0, _pct(totals["paid"], totals["lent"])),
                "clients_active": clients_active,
                "clients_inactive": clients_inactive,
                "active_rate": _pct(clients_active, clients_total),
                "routes_total": len(scope.routes),
                "routes_with_loans": sum(1 for route in scope.routes if by_route_rows.get(route["id"], _EMPTY_TOTALS)["loans"] > 0),
                "collectors_in_field": len(in_field),
                "critical_clients": critical_clients,
            },
            "daily": daily,
            "composition": {
                "up_to_date": _money(portfolio_total - late_total),
                "mild": _money(totals["mild"]),
                "critical": _money(totals["critical"]),
            },
            "by_route": by_route,
            "by_collector": collector_rows,
            "average_goal": _money(sum(row["goal"] for row in collector_rows) / len(collector_rows)) if collector_rows else 0.0,
            "critical_days": CRITICAL_DAYS,
        }

    async def _route_totals(self, route_ids: Sequence[UUID], today: date) -> Dict[UUID, dict]:
        if not route_ids:
            return {}
        stats = build_loan_stats(today)
        in_portfolio = stats.c.balance > 0
        late = stats.c.overdue_amount > 0
        stmt = (
            select(
                ClientRouteModel.route_id.label("route_id"),
                func.count().filter(in_portfolio).label("loans"),
                func.coalesce(func.sum(stats.c.balance).filter(in_portfolio), 0).label("active"),
                func.coalesce(func.sum(stats.c.value_total_loan).filter(in_portfolio), 0).label("lent"),
                func.coalesce(func.sum(stats.c.paid).filter(in_portfolio), 0).label("paid"),
                func.count().filter(late).label("late_loans"),
                func.coalesce(func.sum(stats.c.overdue_amount).filter(late), 0).label("late"),
                func.coalesce(func.sum(stats.c.overdue_amount).filter(late & (stats.c.days_overdue < CRITICAL_DAYS)), 0).label("mild"),
                func.coalesce(func.sum(stats.c.overdue_amount).filter(late & (stats.c.days_overdue >= CRITICAL_DAYS)), 0).label("critical"),
            )
            .select_from(LoanModel)
            .join(stats, stats.c.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(LoanModel.active == True, ClientRouteModel.route_id.in_(route_ids))
            .group_by(ClientRouteModel.route_id)
        )
        rows = (await self.db.execute(stmt)).mappings().all()
        return {row["route_id"]: {key: float(row[key]) for key in _EMPTY_TOTALS} for row in rows}

    async def _client_counts(self, route_ids: Sequence[UUID]) -> Tuple[int, int]:
        if not route_ids:
            return 0, 0
        stmt = (
            select(ClientModel.active, func.count(func.distinct(ClientModel.id)))
            .select_from(ClientModel)
            .join(ClientRouteModel, ClientRouteModel.cliente_id == ClientModel.id)
            .where(ClientRouteModel.route_id.in_(route_ids))
            .group_by(ClientModel.active)
        )
        counts = {bool(active): total for active, total in (await self.db.execute(stmt)).all()}
        return counts.get(True, 0), counts.get(False, 0)

    async def _critical_clients(self, route_ids: Sequence[UUID], today: date) -> int:
        if not route_ids:
            return 0
        stats = build_loan_stats(today)
        stmt = (
            select(func.count(func.distinct(ClientRouteModel.cliente_id)))
            .select_from(LoanModel)
            .join(stats, stats.c.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(
                LoanModel.active == True,
                ClientRouteModel.route_id.in_(route_ids),
                stats.c.overdue_amount > 0,
                stats.c.days_overdue >= CRITICAL_DAYS,
            )
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def _daily(self, route_ids: Sequence[UUID], today: date, days: int) -> List[dict]:
        if not route_ids:
            return []
        start = today - timedelta(days=days - 1)
        goal_rows = (await self.db.execute(
            select(PaymentModel.pay_date, func.coalesce(func.sum(PaymentModel.value), 0))
            .select_from(PaymentModel)
            .join(LoanModel, PaymentModel.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(ClientRouteModel.route_id.in_(route_ids), PaymentModel.pay_date.between(start, today))
            .group_by(PaymentModel.pay_date)
        )).all()
        collected_rows = (await self.db.execute(
            select(PaymentModel.payment_date, func.coalesce(func.sum(PaymentModel.applied), 0))
            .select_from(PaymentModel)
            .join(LoanModel, PaymentModel.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(ClientRouteModel.route_id.in_(route_ids), PaymentModel.payment_date.between(start, today))
            .group_by(PaymentModel.payment_date)
        )).all()

        points: Dict[date, dict] = {}
        for day, value in goal_rows:
            points.setdefault(day, {"date": day, "collected": 0.0, "goal": 0.0})["goal"] = _money(value)
        for day, value in collected_rows:
            points.setdefault(day, {"date": day, "collected": 0.0, "goal": 0.0})["collected"] = _money(value)
        return [points[day] for day in sorted(points)]

    # ---- mora crítica ------------------------------------------------------------
    async def critical(
        self,
        scope: Scope,
        today: date,
        text: Optional[str],
        params: Optional[PaginationParams],
    ) -> Tuple[List[dict], int]:
        if not scope.routes:
            return [], 0
        stats = build_loan_stats(today)
        stmt = (
            select(
                ClientModel.id.label("client_id"),
                ClientModel.full_name.label("client_name"),
                ClientModel.id_document.label("client_document"),
                RouteModel.id.label("route_id"),
                RouteModel.name.label("route_name"),
                LoanModel.id.label("loan_id"),
                LoanModel.loan_number,
                stats.c.balance.label("loan_balance"),
                stats.c.overdue_amount,
                stats.c.overdue_quotas,
                stats.c.overdue_since,
                stats.c.days_overdue,
            )
            .select_from(LoanModel)
            .join(stats, stats.c.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .join(ClientModel, ClientRouteModel.cliente_id == ClientModel.id)
            .join(RouteModel, ClientRouteModel.route_id == RouteModel.id)
            .where(LoanModel.active == True, stats.c.overdue_amount > 0, RouteModel.id.in_(scope.route_ids))
        )
        if text and text.strip():
            like = f"%{text.strip()}%"
            stmt = stmt.where(ClientModel.full_name.ilike(like) | cast(LoanModel.loan_number, String).ilike(like))
        stmt = stmt.order_by(stats.c.overdue_amount.desc(), LoanModel.id)

        rows, total = await paginate_mappings(self.db, stmt, params)
        routes_by_id = {route["id"]: route for route in scope.routes}
        items = []
        for row in rows:
            row["loan_balance"] = _money(row["loan_balance"])
            row["overdue_amount"] = _money(row["overdue_amount"])
            row["collector_names"] = [c["full_name"] for c in scope.collectors_of(routes_by_id[row["route_id"]])]
            row["severity"] = "critical" if row["days_overdue"] >= CRITICAL_DAYS else "warning"
            items.append(row)
        return items, total

    # ---- período -----------------------------------------------------------------
    async def latest_movement_date(self, route_ids: Sequence[UUID]) -> Optional[date]:
        if not route_ids:
            return None
        last_payment = (await self.db.execute(
            select(func.max(PaymentModel.payment_date))
            .select_from(PaymentModel)
            .join(LoanModel, PaymentModel.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(ClientRouteModel.route_id.in_(route_ids))
        )).scalar_one()
        last_expense = (await self.db.execute(
            select(func.max(ExpenseModel.date)).where(ExpenseModel.active == True, ExpenseModel.route_id.in_(route_ids))
        )).scalar_one()
        dates = [d for d in (last_payment, last_expense) if d]
        return max(dates) if dates else None

    async def period_totals(self, route_ids: Sequence[UUID], start: date, end: date) -> Tuple[Dict[date, float], Dict[date, float]]:
        """Recaudo (Σ applied por payment_date) y gastos (Σ value activos por date) por día dentro de [start, end]."""
        if not route_ids:
            return {}, {}
        income_rows = (await self.db.execute(
            select(PaymentModel.payment_date, func.coalesce(func.sum(PaymentModel.applied), 0))
            .select_from(PaymentModel)
            .join(LoanModel, PaymentModel.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(ClientRouteModel.route_id.in_(route_ids), PaymentModel.payment_date.between(start, end))
            .group_by(PaymentModel.payment_date)
        )).all()
        expense_rows = (await self.db.execute(
            select(ExpenseModel.date, func.coalesce(func.sum(ExpenseModel.value), 0))
            .where(ExpenseModel.active == True, ExpenseModel.route_id.in_(route_ids), ExpenseModel.date.between(start, end))
            .group_by(ExpenseModel.date)
        )).all()
        incomes: Dict[date, float] = defaultdict(float)
        costs: Dict[date, float] = defaultdict(float)
        for day, value in income_rows:
            incomes[day] += float(value)
        for day, value in expense_rows:
            costs[day] += float(value)
        return incomes, costs


_EMPTY_TOTALS = {"loans": 0.0, "active": 0.0, "lent": 0.0, "paid": 0.0, "late_loans": 0.0, "late": 0.0, "mild": 0.0, "critical": 0.0}


def _money(value) -> float:
    return round(float(value or 0), 2)


def _pct(part, whole) -> float:
    return round(float(part) / float(whole) * 100, 2) if whole else 0.0
