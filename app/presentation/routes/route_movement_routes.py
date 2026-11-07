from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.route_movement_repository import RouteMovementRepository
from ...use_cases.route_movement_cases import RouteMovementUseCases
from ..shemas.route_movement_shema import RouteMovementRead, RouteMovementCreate, RouteCashSummary
from app.infrastructure.models.user_model import UserModel
from ...infrastructure.utils.require_role import require_role
from ...core.pagination import Page, PaginationParams, pagination_params

_CASH_ROLES = ("01", "02", "03")

router = APIRouter()


def get_route_movement_repository(db: AsyncSession = Depends(get_db)) -> RouteMovementRepository:
    return RouteMovementRepository(db)


def get_route_movement_usecases(
    user: UserModel = Depends(require_role(*_CASH_ROLES)),
    repository: RouteMovementRepository = Depends(get_route_movement_repository),
) -> RouteMovementUseCases:
    usecases = RouteMovementUseCases(repository=repository)
    usecases.user = user
    repository.user = user
    return usecases


@router.get("/", response_model=Page[RouteMovementRead])
async def list_route_movements(
    route_id: UUID,
    pagination: PaginationParams = Depends(pagination_params),
    usecases: RouteMovementUseCases = Depends(get_route_movement_usecases),
):
    return await usecases.list_movements(route_id, pagination)


@router.get("/summary", response_model=RouteCashSummary)
async def get_route_cash_summary(route_id: UUID, usecases: RouteMovementUseCases = Depends(get_route_movement_usecases)):
    return await usecases.get_summary(route_id)


@router.post("/", response_model=RouteMovementRead, status_code=status.HTTP_201_CREATED)
async def create_route_movement(movement_in: RouteMovementCreate, usecases: RouteMovementUseCases = Depends(get_route_movement_usecases)):
    return await usecases.create_movement(movement_in)
