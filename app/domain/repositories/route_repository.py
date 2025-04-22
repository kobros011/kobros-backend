from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.route import Route
from typing import Optional, List
from app.infrastructure.models.route_model import RouteModel


class AbstractRouteRepository(ABC):
    @abstractmethod
    async def get_route_by_id(self, route_id: UUID) -> Optional[Route]:
        pass

    @abstractmethod
    async def list_routes(self) -> List[Route]:
        pass

    @abstractmethod
    async def create_route(self, route: Route) -> Optional[Route]:
        pass

    @abstractmethod
    async def update_route(self, route: Route) -> Optional[Route]:
        pass

    @abstractmethod
    async def delete_route(self, route_id: UUID):
        pass

    @staticmethod
    def model_to_entity(model: RouteModel) -> Route:
        return Route( 
            id=model.id,
            initial_value=model.initial_value,
            initial_expense=model.initial_expense,
            opening_date=model.opening_date,
            brand_id=model.brand_id,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def entity_to_model(entity: Route) -> RouteModel:
        return RouteModel(
            id=entity.id,
            initial_value=entity.initial_value,
            initial_expense=entity.initial_expense,
            opening_date=entity.opening_date,
            brand_id=entity.brand_id,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def update_values(update_data: dict[str, any], current_model: RouteModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model