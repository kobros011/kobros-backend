from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional

from ...infrastructure.dababase.db import get_db
from ...infrastructure.models.user_model import UserModel
from ...infrastructure.repositories.report_repository import ReportRepository
from ...infrastructure.utils.require_role import require_role
from ...use_cases.report_cases import ReportUseCases
from ..shemas.report_shema import PortfolioItemRead, DelinquencyItemRead, PaymentHistoryItemRead

router = APIRouter()

_REPORT_ROLES = ("01", "02", "03", "04")  # dev, super, admin, partner


def get_report_usecases(db: AsyncSession = Depends(get_db)) -> ReportUseCases:
    return ReportUseCases(repository=ReportRepository(db))


@router.get("/portfolio", response_model=List[PortfolioItemRead])
async def portfolio(
    route_id: Optional[UUID] = None,
    brand_id: Optional[UUID] = None,
    _: UserModel = Depends(require_role(*_REPORT_ROLES)),
    usecases: ReportUseCases = Depends(get_report_usecases),
):
    return await usecases.get_portfolio(route_id=route_id, brand_id=brand_id)


@router.get("/delinquency", response_model=List[DelinquencyItemRead])
async def delinquency(
    route_id: Optional[UUID] = None,
    brand_id: Optional[UUID] = None,
    _: UserModel = Depends(require_role(*_REPORT_ROLES)),
    usecases: ReportUseCases = Depends(get_report_usecases),
):
    return await usecases.get_delinquency(route_id=route_id, brand_id=brand_id)


@router.get("/clients/{client_id}/history", response_model=List[PaymentHistoryItemRead])
async def client_payment_history(
    client_id: UUID,
    _: UserModel = Depends(require_role(*_REPORT_ROLES)),
    usecases: ReportUseCases = Depends(get_report_usecases),
):
    return await usecases.get_client_payment_history(client_id)
