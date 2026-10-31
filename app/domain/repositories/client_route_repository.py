from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.client_route import ClientRoute
from typing import Optional, List
from app.infrastructure.models.client_route_model import ClientRouteModel


class AbstractClientRouteRepository(ABC):
    @abstractmethod
    async def get_client_route_by_id(self, client_route_id: UUID) -> Optional[ClientRoute]:
        pass

    @abstractmethod
    async def list_client_routes(self,route_id: Optional[UUID]) -> List[ClientRoute]:
        pass

    @abstractmethod
    async def create_client_route(self, client_route: ClientRoute) -> Optional[ClientRoute]:
        pass

    @abstractmethod
    async def update_client_route(self, client_route: ClientRoute) -> Optional[ClientRoute]:
        pass

    @staticmethod
    def model_to_entity(model: ClientRouteModel) -> ClientRoute:
        return ClientRoute( 
            id=model.id,
            order=model.order,
            client_id=model.cliente_id,
            route_id=model.route_id,
            full_name=model.client.full_name,
            id_document=model.client.id_document,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def entity_to_model(entity: ClientRoute) -> ClientRouteModel:
        return ClientRouteModel(
            id=entity.id,
            order=entity.order,
            route_id=entity.route_id,
            cliente_id=entity.client_id,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def update_values(update_data: dict[str, any], current_model: ClientRouteModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model
