from uuid import UUID
from typing import Optional, List
from ..domain.repositories.route_repository import AbstractRouteRepository
from ..domain.entities.route import Route
from ..presentation.shemas.route_shema import RouteCreate, RouteUpdate, RouteFilters
from app.infrastructure.models.user_model import UserModel
from app.core.pagination import PaginationParams, page_or_list
from app.infrastructure.models.route_model import RouteModel
from app.infrastructure.utils.route_currency import brand_currencies, ensure_can_change_currency, resolve_new_route_currency, validate_route_currency

class RouteUseCases:
    user: Optional[UserModel] = None

    def __init__(self, repository: AbstractRouteRepository):
        self.repository = repository

    async def get_route(self, route_id: UUID) -> Optional[Route]:
        return await self.repository.get_route_by_id(route_id)
    
    async def list_routes(self, filters: RouteFilters, params: Optional[PaginationParams] = None):
        items, total = await self.repository.list_routes(filters, params)
        return page_or_list(items, total, params)
    
    async def create_route(self, route: RouteCreate) -> Optional[Route]:
        currency = await resolve_new_route_currency(self.repository.db, route.brand_id, route.currency)
        new_route = Route(**{**route.model_dump(), 'currency': currency})
        return await self.repository.create_route(new_route)
    
    async def update_route(self, route: RouteUpdate) -> Optional[Route]:
        if route.currency is not None:
            current = await self.repository.db.get(RouteModel, route.id)
            requested = route.currency.strip().upper()
            if current and requested != current.currency:
                validate_route_currency(requested, await brand_currencies(self.repository.db, current.brand_id))
                await ensure_can_change_currency(self.repository.db, route.id)
            route.currency = requested
        return await self.repository.update_route(route)

    async def toggle_route(self, route_id: UUID) -> Optional[Route]:
        return await self.repository.toggle_route(route_id)