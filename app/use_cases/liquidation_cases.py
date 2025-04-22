from uuid import UUID
from typing import Optional, List
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
        new_liquidation = Liquidation(**liquidation.model_dump())
        return await self.repository.create_liquidation(new_liquidation)
    
    async def update_liquidation(self, liquidation: LiquidationUpdate) -> Optional[Liquidation]:
        return await self.repository.update_liquidation(liquidation)
    
    async def delete_liquidation(self, liquidation_id: UUID):
        return await self.repository.delete_liquidation(liquidation_id)