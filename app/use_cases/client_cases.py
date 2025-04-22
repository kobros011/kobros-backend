from uuid import UUID
from typing import Optional, List
from ..domain.repositories.client_repository import AbstractClientRepository
from ..domain.entities.client import Client
from ..presentation.shemas.client_shema import ClientCreate, ClientUpdate

class ClientUseCases:
    def __init__(self, repository: AbstractClientRepository):
        self.repository = repository

    async def get_client(self, client_id: UUID) -> Optional[Client]:
        return await self.repository.get_client_by_id(client_id)
    
    async def list_clients(self) -> List[Client]:
        return await self.repository.list_clients()
    
    async def create_client(self, client: ClientCreate) -> Optional[Client]:
        new_client = Client(**client.model_dump())
        return await self.repository.create_client(new_client)
    
    async def update_client(self, client: ClientUpdate) -> Optional[Client]:
        return await self.repository.update_client(client)
    
    async def delete_client(self, client_id: UUID):
        return await self.repository.delete_client(client_id)
