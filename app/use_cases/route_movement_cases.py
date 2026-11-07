from uuid import UUID
from typing import Optional
from fastapi import HTTPException

from ..domain.repositories.route_movement_repository import AbstractRouteMovementRepository
from ..domain.entities.route_movement import RouteMovement
from ..infrastructure.models.user_model import UserModel
from ..infrastructure.models.route_model import RouteModel
from ..infrastructure.models.models import UserType
from ..core.exceptions import AppException, NotFoundException
from ..core.pagination import PaginationParams, Page, build_page
from ..presentation.shemas.route_movement_shema import RouteMovementCreate


class RouteMovementUseCases:
    user: Optional[UserModel] = None

    def __init__(self, repository: AbstractRouteMovementRepository):
        self.repository = repository

    async def _ensure_route_access(self, route_id: UUID) -> RouteModel:
        route = await self.repository.get_route(route_id)

        if self.user and self.user.brand_id and route.brand_id != self.user.brand_id:
            raise NotFoundException("Ruta no encontrada")

        if self.user and self.user.type_user not in (UserType.dev, UserType.super) \
                and self.user.id not in (route.allowed_users_ids or []):
            raise HTTPException(status_code=403, detail="Sin permisos suficientes")

        return route

    async def list_movements(self, route_id: UUID, params: PaginationParams) -> Page[RouteMovement]:
        await self._ensure_route_access(route_id)
        items, total = await self.repository.list_movements(route_id, params)
        return build_page(list(items), total, params)

    async def get_summary(self, route_id: UUID) -> dict:
        route = await self._ensure_route_access(route_id)
        return await self.repository.get_summary_for_route(route)

    async def create_movement(self, movement_in: RouteMovementCreate) -> RouteMovement:
        await self._ensure_route_access(movement_in.route_id)

        if movement_in.value <= 0:
            raise HTTPException(status_code=400, detail="El valor del movimiento debe ser mayor a 0.")

        concept = (movement_in.concept or "").strip()
        if not concept:
            raise HTTPException(status_code=400, detail="El motivo es requerido.")

        try:
            return await self.repository.create_movement(
                route_id=movement_in.route_id,
                movement_type=movement_in.type,
                value=movement_in.value,
                concept=concept,
            )
        except AppException as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)
