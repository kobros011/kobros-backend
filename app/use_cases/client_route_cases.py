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

    async def move_client_route(self, client_route_id: UUID, position: int) -> List[ClientRoute]:
        return await self.repository.move_client_route(client_route_id, position)

    async def reorder_route(self, route_id: UUID, ordered_ids: List[UUID]) -> List[ClientRoute]:
        return await self.repository.reorder_route(route_id, ordered_ids)

    async def bulk_move(self, route_id: UUID, client_route_ids: List[UUID], target: str, position: Optional[int]) -> List[ClientRoute]:
        return await self.repository.bulk_move(route_id, client_route_ids, target, position)
