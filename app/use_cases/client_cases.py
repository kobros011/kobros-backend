from uuid import UUID
from typing import Optional, List
from ..domain.repositories.client_repository import AbstractClientRepository
from ..domain.entities.client import Client, ClientById
from ..presentation.shemas.client_shema import ClientCreate, ClientUpdate,ClientFilters
from app.infrastructure.models.user_model import UserModel
from app.core.pagination import PaginationParams, page_or_list

class ClientUseCases:
    user: Optional[UserModel] = None
    def __init__(self, repository: AbstractClientRepository):
        self.repository = repository

    async def get_client(self, client_id: UUID) -> Optional[Client]:
        return await self.repository.get_client_by_id(client_id)
    async def get_client_more_info(self, client_id: UUID, route_id: Optional[UUID]) -> Optional[ClientById]:
        return await self.repository.get_by_id_more_info(client_id, route_id)
    
    async def list_clients(self, filters: ClientFilters, params: Optional[PaginationParams] = None):
        items, total = await self.repository.list_clients(filters, params)
        return page_or_list(items, total, params)
    
    async def create_client(self, client: ClientCreate) -> Optional[Client]:
        return await self.repository.create_client(client)
    
    async def update_client(self, client: ClientUpdate) -> Optional[Client]:
        return await self.repository.update_client(client)
    
    async def toggle_client(self, client_id: UUID):
        return await self.repository.toggle_client(client_id)
