from uuid import UUID
from typing import Optional, List
from datetime import date as date_type
from ..domain.repositories.liquidation_repository import AbstractLiquidationRepository
from ..domain.entities.liquidation import Liquidation
from ..presentation.shemas.liquidation_shema import LiquidationCreate, LiquidationUpdate

class LiquidationUseCases:
    def __init__(self, repository: AbstractLiquidationRepository):
        self.repository = repository

    async def get_liquidation(self, liquidation_id: UUID) -> Optional[Liquidation]:
        return await self.repository.get_liquidation_by_id(liquidation_id)

    async def list_liquidations(self) -> List[Liquidation]:
        return await self.repository.list_liquidations()

    async def create_liquidation(self, liquidation: LiquidationCreate) -> Optional[Liquidation]:
        liq_date = liquidation.date.date() if hasattr(liquidation.date, 'date') else liquidation.date
        new_liquidation = Liquidation(
            date=liq_date,
            today_collection_goal=liquidation.today_collection_goal,
            value_base_delivered=liquidation.value_base_delivered,
            total_value_charged=0,
            total_value_expenses=0,
            value_new_loans=liquidation.value_new_loans,
            route_id=liquidation.route_id,
            collector_id=liquidation.collector_id,
        )
        return await self.repository.create_liquidation(new_liquidation, liquidation.route_id, liq_date)

    async def update_liquidation(self, liquidation: LiquidationUpdate) -> Optional[Liquidation]:
        return await self.repository.update_liquidation(liquidation)

    async def confirm_liquidation(self, liquidation_id: UUID, confirmed_by: UUID) -> Optional[Liquidation]:
        return await self.repository.confirm_liquidation(liquidation_id, confirmed_by)

    async def delete_liquidation(self, liquidation_id: UUID):
        return await self.repository.delete_liquidation(liquidation_id)
