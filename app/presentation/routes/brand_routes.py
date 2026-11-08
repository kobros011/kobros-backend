from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List, Union

from ...core.pagination import Page, PaginationParams, filters_from_request, optional_pagination_params
from ...infrastructure.dababase.db import get_db
from ...infrastructure.models.user_model import UserModel
from ...infrastructure.repositories.brand_repository import BrandRepository
from ...infrastructure.utils.require_authentication import require_authentication
from ...infrastructure.utils.require_role import require_role
from ...infrastructure.utils.access import ensure_brand_access
from ...use_cases.brand_cases import BrandUseCases
from ..shemas.brand_shema import BrandRead, BrandUpdate, BrandCreate

router = APIRouter(dependencies=[Depends(require_authentication)])

_ADMIN_ROLES = ("01", "02", "03")  # dev, super, admin
_SUPER_ROLES = ("01", "02")        # dev, super


def get_brand_repository(db: AsyncSession = Depends(get_db)) -> BrandRepository:
    return BrandRepository(db)


def get_brand_usecases(
    user: UserModel = Depends(require_authentication),
    repository: BrandRepository = Depends(get_brand_repository),
) -> BrandUseCases:
    usecases = BrandUseCases(repository=repository)
    usecases.user = user
    repository.user = user
    return usecases


@router.get("/{brand_id}", response_model=Optional[BrandRead])
async def read_brand(
    brand_id: UUID,
    usecases: BrandUseCases = Depends(get_brand_usecases),
    user: UserModel = Depends(require_authentication),
):
    ensure_brand_access(brand_id, user)
    return await usecases.get_brand(brand_id)


@router.get("/", response_model=Union[Page[BrandRead], List[BrandRead]])
async def list_brands(
    request: Request,
    pagination: Optional[PaginationParams] = Depends(optional_pagination_params),
    usecases: BrandUseCases = Depends(get_brand_usecases),
):
    return await usecases.list_brands(filters_from_request(request), pagination)


@router.post("/", response_model=BrandRead, status_code=status.HTTP_201_CREATED)
async def create_brand(
    brand_in: BrandCreate,
    _: UserModel = Depends(require_role(*_SUPER_ROLES)),
    usecases: BrandUseCases = Depends(get_brand_usecases),
):
    return await usecases.create_brand(brand=brand_in)


@router.put("/{brand_id}", response_model=BrandRead)
async def update_brand(
    brand_in: BrandUpdate,
    _: UserModel = Depends(require_role(*_SUPER_ROLES)),
    usecases: BrandUseCases = Depends(get_brand_usecases),
):
    return await usecases.update_brand(brand=brand_in)


@router.put("/{brand_id}/toggle")
async def toggle_brand(
    brand_id: UUID,
    _: UserModel = Depends(require_role(*_SUPER_ROLES)),
    usecases: BrandUseCases = Depends(get_brand_usecases),
):
    return await usecases.toggle_brand(brand_id)