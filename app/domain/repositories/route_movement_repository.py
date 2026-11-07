from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional, Sequence
from app.domain.entities.route_movement import RouteMovement
from app.infrastructure.models.route_movement_model import RouteMovementModel
from app.infrastructure.models.route_model import RouteModel
from app.infrastructure.models.user_model import UserModel
from app.core.pagination import PaginationParams


class AbstractRouteMovementRepository(ABC):
    user: Optional[UserModel] = None

    @abstractmethod
    async def get_route(self, route_id: UUID) -> RouteModel:
        """Carga la ruta sin bloqueo, para validar acceso/calcular el resumen."""
        pass

    @abstractmethod
    async def list_movements(self, route_id: UUID, params: PaginationParams) -> tuple[Sequence[RouteMovement], int]:
        pass

    @abstractmethod
    async def get_summary_for_route(self, route: RouteModel) -> dict:
        pass

    @abstractmethod
    async def create_movement(self, route_id: UUID, movement_type: str, value: float, concept: str) -> RouteMovement:
        pass

    @staticmethod
    def model_to_entity(model: RouteMovementModel) -> RouteMovement:
        return RouteMovement(
            id=model.id,
            route_id=model.route_id,
            type=model.type,
            value=model.value,
            concept=model.concept,
            user_id=model.user_id,
            user_name=model.user.full_name if model.user else "",
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
