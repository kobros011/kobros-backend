from uuid import UUID
from typing import Optional, List
from ..domain.repositories.route_repository import AbstractRouteRepository
from ..domain.entities.route import Route
from ..presentation.shemas.route_shema import RouteCreate, RouteUpdate, RouteFilters
from app.infrastructure.models.user_model import UserModel

class RouteUseCases:
    user: Optional[UserModel] = None

    def __init__(self, repository: AbstractRouteRepository):
        self.repository = repository

    async def get_route(self, route_id: UUID) -> Optional[Route]:
        return await self.repository.get_route_by_id(route_id)
    
    async def list_routes(self, filters: RouteFilters) -> List[Route]:
        return await self.repository.list_routes(filters)
    
    async def create_route(self, route: RouteCreate) -> Optional[Route]:
        new_route = Route(**route.model_dump())
        return await self.repository.create_route(new_route)
    
    async def update_route(self, route: RouteUpdate) -> Optional[Route]:
        return await self.repository.update_route(route)

    async def toggle_route(self, route_id: UUID) -> Optional[Route]:
        return await self.repository.toggle_route(route_id)