from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.client import Client
from typing import Optional, List
from app.infrastructure.models.client_model import ClientModel


class AbstractClientRepository(ABC):
    @abstractmethod
    async def get_client_by_id(self, client_id: UUID) -> Optional[Client]:
        pass

    @abstractmethod
    async def list_clients(self) -> List[Client]:
        pass

    @abstractmethod
    async def create_client(self, client: Client) -> Optional[Client]:
        pass

    @abstractmethod
    async def update_client(self, client: Client) -> Optional[Client]:
        pass

    @abstractmethod
    async def delete_client(self, client_id: UUID):
        pass

    @staticmethod
    def model_to_entity(model: ClientModel) -> Client:
        return Client(
            id=model.id,
            full_name=model.full_name,
            id_document=model.id_document,
            current_address=model.current_address,
            current_phone=model.current_phone,
            active=model.active,
            brand_id= model.brand_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def entity_to_model(entity: Client) -> ClientModel:
        return ClientModel(
            id=entity.id,
            full_name=entity.full_name,
            id_document=entity.id_document,
            current_address=entity.current_address,
            current_phone=entity.current_phone,
            brand_id= entity.brand_id,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def update_values(update_data: dict[str, any], current_model: ClientModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model
