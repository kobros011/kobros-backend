from datetime import date, timedelta
from typing import Dict, Optional
from uuid import UUID

from app.core.clock import today_bogota
from app.core.pagination import PaginationParams, build_page
from app.infrastructure.models.user_model import UserModel
from app.infrastructure.repositories.dashboard_repository import DashboardRepository, Scope

MONTHS = 12
WEEK_DAYS = 7


def _role(user: UserModel) -> str:
    return user.type_user.value if hasattr(user.type_user, "value") else str(user.type_user)


class DashboardUseCases:
    user: Optional[UserModel] = None

    def __init__(self, repository: DashboardRepository):
        self.repository = repository

    def _effective_brand_id(self, requested: Optional[UUID]) -> Optional[UUID]:
        """Solo el dev (01) elige marca; el resto queda fijo en la suya aunque el cliente mande otra."""
        if _role(self.user) == "01":
            return requested
        return self.user.brand_id

    async def _scope(self, brand_id: Optional[UUID], route_id: Optional[UUID], collector_id: Optional[UUID], currency: Optional[str] = None) -> Scope:
        return await self.repository.resolve_scope(self.user, self._effective_brand_id(brand_id), route_id, collector_id, currency)

    async def filters(self, brand_id: Optional[UUID]) -> dict:
        scope = await self._scope(brand_id, None, None)
        return {"routes": scope.all_routes, "collectors": scope.all_collectors}

    async def summary(self, brand_id: Optional[UUID], route_id: Optional[UUID], collector_id: Optional[UUID], days: int, currency: Optional[str] = None) -> dict:
        scope = await self._scope(brand_id, route_id, collector_id, currency)
        return await self.repository.summary(scope, today_bogota(), days)

    async def critical(
        self,
        brand_id: Optional[UUID],
        route_id: Optional[UUID],
        collector_id: Optional[UUID],
        text: Optional[str],
        params: PaginationParams,
        currency: Optional[str] = None,
    ):
        scope = await self._scope(brand_id, route_id, collector_id, currency)
        items, total = await self.repository.critical(scope, today_bogota(), text, params)
        return build_page(items, total, params)

    async def period(
        self,
        brand_id: Optional[UUID],
        route_id: Optional[UUID],
        collector_id: Optional[UUID],
        mode: str,
        on_date: Optional[date],
        currency: Optional[str] = None,
    ) -> dict:
        scope = await self._scope(brand_id, route_id, collector_id, currency)
        route_ids = scope.route_ids
        latest = await self.repository.latest_movement_date(route_ids)
        reference = on_date or latest or today_bogota()

        if mode == "weekly":
            start = reference - timedelta(days=reference.weekday())  # lunes
            end = start + timedelta(days=WEEK_DAYS - 1)
        else:
            start, end = date(reference.year, 1, 1), date(reference.year, 12, 31)

        incomes, costs = await self.repository.period_totals(route_ids, start, end)

        if mode == "weekly":
            bucket_starts = [start + timedelta(days=i) for i in range(WEEK_DAYS)]
            bucket_of = lambda day: day  # noqa: E731
            key_of = lambda day: day.isoformat()  # noqa: E731
        else:
            bucket_starts = [date(start.year, month, 1) for month in range(1, MONTHS + 1)]
            bucket_of = lambda day: date(day.year, day.month, 1)  # noqa: E731
            key_of = lambda day: f"{day.year}-{day.month:02d}"  # noqa: E731

        collected: Dict[date, float] = {b: 0.0 for b in bucket_starts}
        expenses: Dict[date, float] = {b: 0.0 for b in bucket_starts}
        for day, value in incomes.items():
            collected[bucket_of(day)] += value
        for day, value in costs.items():
            expenses[bucket_of(day)] += value

        buckets = [
            {
                "key": key_of(b),
                "date": b,
                "collected": round(collected[b], 2),
                "expenses": round(expenses[b], 2),
                "profit": round(collected[b] - expenses[b], 2),
            }
            for b in bucket_starts
        ]
        total_collected = round(sum(collected.values()), 2)
        total_expenses = round(sum(expenses.values()), 2)
        profit = round(total_collected - total_expenses, 2)
        return {
            "mode": mode,
            "start": start,
            "end": end,
            "latest_movement_date": latest,
            "buckets": buckets,
            "totals": {
                "collected": total_collected,
                "expenses": total_expenses,
                "profit": profit,
                "margin": round(profit / total_collected * 100, 2) if total_collected else 0.0,
            },
        }
