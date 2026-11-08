from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.pagination import Page, PaginationParams
from ...infrastructure.dababase.db import get_db
from ...infrastructure.models.user_model import UserModel
from ...infrastructure.repositories.dashboard_repository import DashboardRepository
from ...infrastructure.utils.require_role import require_role
from ...use_cases.dashboard_cases import DashboardUseCases
from ..shemas.dashboard_shema import (
    CriticalLoanRead,
    DashboardFiltersRead,
    DashboardSummaryRead,
    PeriodMode,
    PeriodReportRead,
)

router = APIRouter()

_REPORT_ROLES = ("01", "02", "03", "04")  # dev, super, admin, partner
CRITICAL_PAGE_SIZE = 5


def get_dashboard_usecases(
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_role(*_REPORT_ROLES)),
) -> DashboardUseCases:
    usecases = DashboardUseCases(repository=DashboardRepository(db))
    usecases.user = user
    return usecases


def critical_pagination(
    page: int = Query(1, ge=1),
    page_size: int = Query(CRITICAL_PAGE_SIZE, ge=1, le=100),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


@router.get("/dashboard/filters", response_model=DashboardFiltersRead)
async def dashboard_filters(
    brand_id: Optional[UUID] = None,
    usecases: DashboardUseCases = Depends(get_dashboard_usecases),
):
    return await usecases.filters(brand_id)


@router.get("/dashboard/summary", response_model=DashboardSummaryRead)
async def dashboard_summary(
    route_id: Optional[UUID] = None,
    collector_id: Optional[UUID] = None,
    brand_id: Optional[UUID] = None,
    days: int = Query(90, ge=1, le=365),
    currency: Optional[str] = None,
    usecases: DashboardUseCases = Depends(get_dashboard_usecases),
):
    return await usecases.summary(brand_id, route_id, collector_id, days, currency)


@router.get("/dashboard/critical", response_model=Page[CriticalLoanRead])
async def dashboard_critical(
    route_id: Optional[UUID] = None,
    collector_id: Optional[UUID] = None,
    brand_id: Optional[UUID] = None,
    text: Optional[str] = None,
    pagination: PaginationParams = Depends(critical_pagination),
    currency: Optional[str] = None,
    usecases: DashboardUseCases = Depends(get_dashboard_usecases),
):
    return await usecases.critical(brand_id, route_id, collector_id, text, pagination, currency)


@router.get("/period", response_model=PeriodReportRead)
async def period_report(
    mode: PeriodMode,
    on_date: Optional[date] = Query(None, alias="date"),
    route_id: Optional[UUID] = None,
    collector_id: Optional[UUID] = None,
    brand_id: Optional[UUID] = None,
    currency: Optional[str] = None,
    usecases: DashboardUseCases = Depends(get_dashboard_usecases),
):
    return await usecases.period(brand_id, route_id, collector_id, mode, on_date, currency)
