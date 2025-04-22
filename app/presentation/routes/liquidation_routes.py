from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.liquidation_repository import LiquidationRepository
from ...use_cases.liquidation_cases import LiquidationUseCases
from ..shemas.liquidation_shema import LiquidationRead, LiquidationUpdate, LiquidationCreate
from ...use_cases.liquidation_cases import LiquidationUseCases
from ...infrastructure.utils.require_authentication import require_authentication

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_liquidation_repository(db: AsyncSession = Depends(get_db)) -> LiquidationRepository:
    return LiquidationRepository(db)

def get_liquidation_usecases(repository: LiquidationRepository = Depends(get_liquidation_repository)) -> LiquidationUseCases:
    return LiquidationUseCases(repository)

@router.get("/{liquidation_id}", response_model=Optional[LiquidationRead])
async def read_liquidation(liquidation_id: UUID, usecases: LiquidationUseCases = Depends(get_liquidation_usecases)):
    return await usecases.get_liquidation(liquidation_id)

@router.get("/", response_model=List[LiquidationRead])
async def list_liquidations(usecases: LiquidationUseCases = Depends(get_liquidation_usecases)):
    return await usecases.list_liquidations()

@router.post("/", response_model=LiquidationRead, status_code=status.HTTP_201_CREATED)
async def create_liquidation(liquidation_in: LiquidationCreate, usecases: LiquidationUseCases = Depends(get_liquidation_usecases)):
    return await usecases.create_liquidation(liquidation=liquidation_in)

@router.put("/{liquidation_id}", response_model=LiquidationRead)
async def update_liquidation(liquidation_in: LiquidationUpdate, usecases: LiquidationUseCases = Depends(get_liquidation_usecases)):
    return await usecases.update_liquidation(liquidation=liquidation_in)

@router.delete("/{liquidation_id}")
async def delete_liquidation(liquidation_id: UUID, usecases: LiquidationUseCases = Depends(get_liquidation_usecases)):
    return await usecases.delete_liquidation(liquidation_id)