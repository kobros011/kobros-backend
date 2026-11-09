from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional, Union

from ...infrastructure.dababase.db import get_db
from ...infrastructure.models.user_model import UserModel
from ...infrastructure.repositories.report_repository import ReportRepository
from ...infrastructure.utils.access import ensure_client_access
from ...infrastructure.utils.require_role import require_role
from ...use_cases.report_cases import ReportUseCases
from ...core.pagination import Page, optional_pagination_params, PaginationParams
from ..shemas.report_shema import PortfolioItemRead, DelinquencyItemRead, PaymentHistoryItemRead, ReportSummaryRead

router = APIRouter()

_REPORT_ROLES = ("01", "02", "03", "04")  # dev, super, admin, partner


def get_report_usecases(
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_role(*_REPORT_ROLES)),
) -> ReportUseCases:
    usecases = ReportUseCases(repository=ReportRepository(db))
    usecases.user = user
    return usecases


@router.get("/portfolio", response_model=Union[Page[PortfolioItemRead], List[PortfolioItemRead]])
async def portfolio(
    route_id: Optional[UUID] = None,
    brand_id: Optional[UUID] = None,
    text: Optional[str] = None,
    currency: Optional[str] = None,
    pagination: Optional[PaginationParams] = Depends(optional_pagination_params),
    usecases: ReportUseCases = Depends(get_report_usecases),
):
    return await usecases.get_portfolio(route_id=route_id, brand_id=brand_id, text=text, params=pagination, currency=currency)


@router.get("/portfolio/summary", response_model=ReportSummaryRead)
async def portfolio_summary(
    route_id: Optional[UUID] = None,
    brand_id: Optional[UUID] = None,
    text: Optional[str] = None,
    currency: Optional[str] = None,
    usecases: ReportUseCases = Depends(get_report_usecases),
):
    return await usecases.get_portfolio_summary(route_id=route_id, brand_id=brand_id, text=text, currency=currency)


@router.get("/delinquency", response_model=Union[Page[DelinquencyItemRead], List[DelinquencyItemRead]])
async def delinquency(
    route_id: Optional[UUID] = None,
    brand_id: Optional[UUID] = None,
    text: Optional[str] = None,
    currency: Optional[str] = None,
    pagination: Optional[PaginationParams] = Depends(optional_pagination_params),
    usecases: ReportUseCases = Depends(get_report_usecases),
):
    return await usecases.get_delinquency(route_id=route_id, brand_id=brand_id, text=text, params=pagination, currency=currency)


@router.get("/delinquency/summary", response_model=ReportSummaryRead)
async def delinquency_summary(
    route_id: Optional[UUID] = None,
    brand_id: Optional[UUID] = None,
    text: Optional[str] = None,
    currency: Optional[str] = None,
    usecases: ReportUseCases = Depends(get_report_usecases),
):
    return await usecases.get_delinquency_summary(route_id=route_id, brand_id=brand_id, text=text, currency=currency)


@router.get("/clients/{client_id}/history", response_model=List[PaymentHistoryItemRead])
async def client_payment_history(
    client_id: UUID,
    user: UserModel = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
    usecases: ReportUseCases = Depends(get_report_usecases),
):
    await ensure_client_access(db, client_id, user)
    return await usecases.get_client_payment_history(client_id)
