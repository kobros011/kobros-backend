from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.clock import today_bogota
from ...core.pagination import Page, PaginationParams, pagination_params
from ...infrastructure.dababase.db import get_db
from ...infrastructure.models.user_model import UserModel
from ...infrastructure.repositories.liquidation_repository import LiquidationRepository
from ...infrastructure.utils.require_role import require_role
from ...use_cases.liquidation_cases import LiquidationUseCases
from ..shemas.liquidation_shema import (
    LiquidationCreate,
    LiquidationDetailRead,
    LiquidationPage,
    LiquidationNoteUpdate,
    LiquidationPreviewRead,
    LiquidationRead,
)

router = APIRouter()

_ALL = ("01", "02", "03", "04", "05")  # dev, super, admin, socio, cobrador
_OPERATE = ("01", "02", "03", "05")     # quienes pueden cerrar caja (el socio solo consulta)


def get_usecases(db: AsyncSession = Depends(get_db), user: UserModel = Depends(require_role(*_ALL))) -> LiquidationUseCases:
    return LiquidationUseCases(LiquidationRepository(db), user)


def operate_usecases(db: AsyncSession = Depends(get_db), user: UserModel = Depends(require_role(*_OPERATE))) -> LiquidationUseCases:
    return LiquidationUseCases(LiquidationRepository(db), user)


@router.get("/preview", response_model=LiquidationPreviewRead)
async def preview_liquidation(
    route_id: UUID,
    day: Optional[date] = Query(None, alias="date"),
    collector_id: Optional[UUID] = None,
    usecases: LiquidationUseCases = Depends(operate_usecases),
):
    return await usecases.preview(route_id, day or today_bogota(), collector_id)


@router.get("/", response_model=LiquidationPage)
async def list_liquidations(
    route_id: Optional[UUID] = None,
    collector_id: Optional[UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(pendiente|confirmada|reabierta)$"),
    pagination: PaginationParams = Depends(pagination_params),
    usecases: LiquidationUseCases = Depends(get_usecases),
):
    return await usecases.list(pagination, route_id=route_id, collector_id=collector_id, date_from=date_from, date_to=date_to, status=status_filter)


@router.get("/{liquidation_id}", response_model=LiquidationDetailRead)
async def read_liquidation(liquidation_id: UUID, usecases: LiquidationUseCases = Depends(get_usecases)):
    return await usecases.detail(liquidation_id)


@router.post("/", response_model=LiquidationRead, status_code=status.HTTP_201_CREATED)
async def create_liquidation(body: LiquidationCreate, usecases: LiquidationUseCases = Depends(operate_usecases)):
    return await usecases.create(body)


@router.post("/{liquidation_id}/confirm", response_model=LiquidationRead)
async def confirm_liquidation(liquidation_id: UUID, usecases: LiquidationUseCases = Depends(get_usecases)):
    return await usecases.confirm(liquidation_id)


@router.post("/{liquidation_id}/reopen", response_model=LiquidationRead)
async def reopen_liquidation(liquidation_id: UUID, usecases: LiquidationUseCases = Depends(get_usecases)):
    return await usecases.reopen(liquidation_id)


@router.put("/{liquidation_id}", response_model=LiquidationRead)
async def update_liquidation_note(liquidation_id: UUID, body: LiquidationNoteUpdate, usecases: LiquidationUseCases = Depends(operate_usecases)):
    return await usecases.update_note(liquidation_id, body.note)


@router.delete("/{liquidation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_liquidation(liquidation_id: UUID, usecases: LiquidationUseCases = Depends(operate_usecases)):
    await usecases.delete(liquidation_id)
