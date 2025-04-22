from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.brand_repository import BrandRepository
from ...use_cases.brand_cases import BrandUseCases
from ..shemas.brand_shema import BrandRead, BrandUpdate, BrandCreate
from ...use_cases.brand_cases import BrandUseCases
from ...infrastructure.utils.require_authentication import require_authentication

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_brand_repository(db: AsyncSession = Depends(get_db)) -> BrandRepository:
    return BrandRepository(db)

def get_brand_usecases(repository: BrandRepository = Depends(get_brand_repository)) -> BrandUseCases:
    return BrandUseCases(repository)

@router.get("/{brand_id}", response_model=Optional[BrandRead])
async def read_brand(brand_id: UUID, usecases: BrandUseCases = Depends(get_brand_usecases)):
    return await usecases.get_brand(brand_id)

@router.get("/", response_model=List[BrandRead])
async def list_brands(usecases: BrandUseCases = Depends(get_brand_usecases)):
    return await usecases.list_brands()

@router.post("/", response_model=BrandRead, status_code=status.HTTP_201_CREATED)
async def create_brand(brand_in: BrandCreate, usecases: BrandUseCases = Depends(get_brand_usecases)):
    return await usecases.create_brand(brand=brand_in)

@router.put("/{brand_id}", response_model=BrandRead)
async def update_brand(brand_in: BrandUpdate, usecases: BrandUseCases = Depends(get_brand_usecases)):
    return await usecases.update_brand(brand=brand_in)

@router.delete("/{brand_id}")
async def delete_brand(brand_id: UUID, usecases: BrandUseCases = Depends(get_brand_usecases)):
    return await usecases.delete_brand(brand_id)