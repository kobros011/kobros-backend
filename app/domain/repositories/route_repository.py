from abc import ABC, abstractmethod, get_cache_token
from uuid import UUID
from app.domain.entities.route import Route
from typing import Optional, List
from app.infrastructure.models.route_model import RouteModel
from app.infrastructure.models.user_model import UserModel

class AbstractRouteRepository(ABC):
    user: Optional[UserModel] = None

    @abstractmethod
    async def get_route_by_id(self, route_id: UUID) -> Optional[Route]:
        pass

    @abstractmethod
    async def list_routes(self, filters) -> List[Route]:
        pass

    @abstractmethod
    async def create_route(self, route: Route) -> Optional[Route]:
        pass

    @abstractmethod
    async def update_route(self, route: Route) -> Optional[Route]:
        pass

    @abstractmethod
    async def toggle_route(self, route_id: UUID):
        pass

    @staticmethod
    def model_to_entity(model: RouteModel) -> Route:
        return Route( 
            id=model.id,
            name=model.name,
            initial_value=model.initial_value,
            initial_expense=model.initial_expense,
            opening_date=model.opening_date,
            brand_id=model.brand_id,
            allowed_users_ids=model.allowed_users_ids,
            loans_number=model.loans_number,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def entity_to_model(entity: Route) -> RouteModel:
        return RouteModel(
            id=entity.id,
            name=entity.name,
            initial_value=entity.initial_value,
            initial_expense=entity.initial_expense,
            opening_date=entity.opening_date,
            brand_id=entity.brand_id,
            allowed_users_ids=entity.allowed_users_ids,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def update_values(update_data: dict[str, any], current_model: RouteModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model