"""Esquemas del Dashboard de Reportes (Resumen, Semanal, Anual). Porcentajes en escala 0–100."""
from datetime import date
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel

Severity = Literal["critical", "warning"]
PeriodMode = Literal["weekly", "annual"]


# ---- filtros ---------------------------------------------------------------
class DashboardRouteFilter(BaseModel):
    id: UUID
    name: str
    collector_ids: List[UUID] = []


class DashboardCollectorFilter(BaseModel):
    id: UUID
    full_name: str


class DashboardFiltersRead(BaseModel):
    routes: List[DashboardRouteFilter]
    collectors: List[DashboardCollectorFilter]


# ---- resumen ---------------------------------------------------------------
class DashboardKpis(BaseModel):
    portfolio_total: float
    portfolio_loans: int
    delinquency_total: float
    delinquency_loans: int
    delinquency_rate: float
    total_lent: float
    total_paid: float
    effectiveness: float
    clients_active: int
    clients_inactive: int
    active_rate: float
    routes_total: int
    routes_with_loans: int
    collectors_in_field: int
    critical_clients: int


class DailyPoint(BaseModel):
    date: date
    collected: float
    goal: float


class Composition(BaseModel):
    up_to_date: float
    mild: float
    critical: float


class RouteRow(BaseModel):
    route_id: UUID
    route_name: str
    collector_names: List[str]
    active: float
    late: float
    rate: float


class CollectorRow(BaseModel):
    collector_id: UUID
    full_name: str
    route_names: List[str]
    goal: float
    collected: float
    percent: float


class DashboardSummaryRead(BaseModel):
    kpis: DashboardKpis
    daily: List[DailyPoint]
    composition: Composition
    by_route: List[RouteRow]
    by_collector: List[CollectorRow]
    average_goal: float
    critical_days: int


# ---- mora crítica ----------------------------------------------------------
class CriticalLoanRead(BaseModel):
    client_id: UUID
    client_name: str
    client_document: Optional[str] = None
    route_id: UUID
    route_name: str
    collector_names: List[str]
    loan_id: UUID
    loan_number: int
    loan_balance: float
    overdue_amount: float
    overdue_quotas: int
    overdue_since: date
    days_overdue: int
    severity: Severity


# ---- período ---------------------------------------------------------------
class PeriodBucket(BaseModel):
    key: str  # 'YYYY-MM-DD' (semanal) o 'YYYY-MM' (anual)
    date: date  # inicio del bucket
    collected: float
    expenses: float
    profit: float


class PeriodTotals(BaseModel):
    collected: float
    expenses: float
    profit: float
    margin: float


class PeriodReportRead(BaseModel):
    mode: PeriodMode
    start: date
    end: date
    latest_movement_date: Optional[date] = None
    buckets: List[PeriodBucket]
    totals: PeriodTotals
