from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.liquidation import Liquidation
from typing import Optional, List
from app.infrastructure.models.liquidation_model import LiquidationModel


class AbstractLiquidationRepository(ABC):
    @abstractmethod
    async def get_liquidation_by_id(self, liquidation_id: UUID) -> Optional[Liquidation]:
        pass

    @abstractmethod
    async def list_liquidations(self) -> List[Liquidation]:
        pass

    @abstractmethod
    async def create_liquidation(self, liquidation: Liquidation, route_id: UUID, date) -> Optional[Liquidation]:
        pass

    @abstractmethod
    async def update_liquidation(self, liquidation: Liquidation) -> Optional[Liquidation]:
        pass

    @abstractmethod
    async def delete_liquidation(self, liquidation_id: UUID):
        pass

    @abstractmethod
    async def confirm_liquidation(self, liquidation_id: UUID, confirmed_by: UUID) -> Optional[Liquidation]:
        pass

    @staticmethod
    def model_to_entity(model: LiquidationModel) -> Liquidation:
        return Liquidation(
            id=model.id,
            date=model.date,
            today_collection_goal=model.today_collection_goal,
            value_base_delivered=model.value_base_delivered,
            total_value_charged=model.total_value_charged,
            total_value_expenses=model.total_value_expenses,
            value_new_loans=model.value_new_loans,
            route_id=model.route_id,
            collector_id=model.collector_id,
            admin_confirmed_at=model.admin_confirmed_at,
            admin_confirmed_by=model.admin_confirmed_by,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def entity_to_model(entity: Liquidation) -> LiquidationModel:
        return LiquidationModel(
            id=entity.id,
            date=entity.date,
            today_collection_goal=entity.today_collection_goal,
            value_base_delivered=entity.value_base_delivered,
            total_value_charged=entity.total_value_charged,
            total_value_expenses=entity.total_value_expenses,
            value_new_loans=entity.value_new_loans,
            route_id=entity.route_id,
            collector_id=entity.collector_id,
            admin_confirmed_at=entity.admin_confirmed_at,
            admin_confirmed_by=entity.admin_confirmed_by,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def update_values(update_data: dict[str, any], current_model: LiquidationModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model
