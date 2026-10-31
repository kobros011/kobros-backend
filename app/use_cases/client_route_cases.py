from uuid import UUID
from typing import Optional, List
from ..domain.repositories.client_route_repository import AbstractClientRouteRepository
from ..domain.entities.client_route import ClientRoute
from ..presentation.shemas.client_route_shema import ClientRouteCreate, ClientRouteUpdate

class ClientRouteUseCases:
    def __init__(self, repository: AbstractClientRouteRepository):
        self.repository = repository

    async def get_client_route(self, client_route_id: UUID) -> Optional[ClientRoute]:
        return await self.repository.get_client_route_by_id(client_route_id)
    
    async def list_client_routes(self, route_id: Optional[UUID]) -> List[ClientRoute]:
        return await self.repository.list_client_routes(route_id)
    
    async def create_client_route(self, client_route: ClientRouteCreate) -> Optional[ClientRoute]:
        new_client_route = ClientRoute(**client_route.model_dump())
        return await self.repository.create_client_route(new_client_route)
    
    async def update_client_route(self, client_route: ClientRouteUpdate) -> Optional[ClientRoute]:
        return await self.repository.update_client_route(client_route)