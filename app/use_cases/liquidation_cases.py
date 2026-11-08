from datetime import date as date_type
from typing import Optional
from uuid import UUID

from sqlalchemy import select

from ..core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from ..core.pagination import Page, PaginationParams, build_page
from ..infrastructure.models.route_model import RouteModel
from ..infrastructure.models.user_model import UserModel
from ..infrastructure.repositories.liquidation_repository import LiquidationRepository
from ..presentation.shemas.liquidation_shema import LiquidationCreate, LiquidationPage

ADMIN_ROLES = ("01", "02", "03")


def _role(user: UserModel) -> str:
    return user.type_user.value if hasattr(user.type_user, "value") else str(user.type_user)


class LiquidationUseCases:
    """Reglas de acceso: marca del usuario; el cobrador (05) y el socio (04) solo ven/operan rutas donde están asignados
    y el cobrador solo sus propios cierres. Confirmar y reabrir son de admin (01-03) de la marca."""

    def __init__(self, repository: LiquidationRepository, user: UserModel):
        self.repository = repository
        self.user = user
        self.role = _role(user)

    # ---- acceso ----
    def _check_route(self, route: RouteModel) -> None:
        if self.role != "01" and self.user.brand_id != route.brand_id:
            raise NotFoundException("Ruta no encontrada")
        if self.role in ("04", "05") and self.user.id not in (route.allowed_users_ids or []):
            raise ForbiddenException("No tienes asignada esta ruta")

    async def _route(self, route_id: UUID) -> RouteModel:
        route = await self.repository.get_route(route_id)
        self._check_route(route)
        return route

    def _resolve_collector(self, route: RouteModel, requested: Optional[UUID]) -> Optional[UUID]:
        if self.role == "05":
            if requested and requested != self.user.id:
                raise ForbiddenException("Un cobrador solo puede cerrar su propia caja")
            return self.user.id
        if requested and requested not in (route.allowed_users_ids or []):
            raise BadRequestException("El cobrador no está asignado a esta ruta")
        return requested

    async def _load(self, liquidation_id: UUID) -> dict:
        data = await self.repository.get_read(liquidation_id)
        route = await self.repository.get_route(data["route_id"])
        if self.role != "01" and self.user.brand_id != route.brand_id:
            raise NotFoundException("Liquidación no encontrada")
        if self.role in ("04", "05") and self.user.id not in (route.allowed_users_ids or []):
            raise NotFoundException("Liquidación no encontrada")
        if self.role == "05" and data["collector_id"] != self.user.id:
            raise NotFoundException("Liquidación no encontrada")
        return data

    def _require_admin(self) -> None:
        if self.role not in ADMIN_ROLES:
            raise ForbiddenException("Solo un administrador puede hacer esta acción")

    # ---- casos de uso ----
    async def preview(self, route_id: UUID, day: date_type, collector_id: Optional[UUID]) -> dict:
        route = await self._route(route_id)
        return await self.repository.preview(route_id, day, self._resolve_collector(route, collector_id))

    async def create(self, body: LiquidationCreate) -> dict:
        if self.role == "04":
            raise ForbiddenException("El socio no puede cerrar caja")
        route = await self._route(body.route_id)
        self.repository.ensure_closable(body.date)
        collector_id = self._resolve_collector(route, body.collector_id)
        return await self.repository.create(route_id=body.route_id, day=body.date, collector_id=collector_id,
                                            base=body.value_base_delivered, cash=body.cash_delivered, note=body.note, closed_by=self.user.id)

    async def list(self, params: PaginationParams, *, route_id: Optional[UUID], collector_id: Optional[UUID], date_from: Optional[date_type],
                   date_to: Optional[date_type], status: Optional[str]) -> Page:
        brand_id = None if self.role == "01" else self.user.brand_id
        route_ids = None
        if self.role in ("04", "05"):
            rows = await self.repository.db.execute(select(RouteModel.id).where(RouteModel.allowed_users_ids.contains([self.user.id]), RouteModel.brand_id == self.user.brand_id))
            route_ids = [r[0] for r in rows.all()]
        if self.role == "05":
            collector_id = self.user.id
        items, total, totals = await self.repository.list_page(
            brand_id=brand_id, route_ids=route_ids, collector_id=collector_id, route_id=route_id, date_from=date_from, date_to=date_to,
            status=status, include_reopened=status == "reabierta", params=params)
        page = build_page(items, total, params)
        return LiquidationPage(**page.model_dump(), summary=totals)

    async def detail(self, liquidation_id: UUID) -> dict:
        await self._load(liquidation_id)
        return await self.repository.detail(liquidation_id)

    async def confirm(self, liquidation_id: UUID) -> dict:
        self._require_admin()
        await self._load(liquidation_id)
        return await self.repository.confirm(liquidation_id, self.user.id)

    async def reopen(self, liquidation_id: UUID) -> dict:
        self._require_admin()
        await self._load(liquidation_id)
        return await self.repository.reopen(liquidation_id, self.user.id)

    async def delete(self, liquidation_id: UUID) -> None:
        if self.role == "04":
            raise ForbiddenException("El socio no puede eliminar cierres")
        await self._load(liquidation_id)
        await self.repository.delete_unconfirmed(liquidation_id)

    async def update_note(self, liquidation_id: UUID, note: Optional[str]) -> dict:
        if self.role == "04":
            raise ForbiddenException("El socio no puede editar cierres")
        await self._load(liquidation_id)
        return await self.repository.update_note(liquidation_id, note)
