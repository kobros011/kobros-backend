from uuid import UUID
from ...domain.entities.liquidation import Liquidation
from ...domain.repositories.liquidation_repository import AbstractLiquidationRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.liquidation_model import LiquidationModel
from ...presentation.shemas.liquidation_shema import LiquidationUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException


class LiquidationRepository(AbstractLiquidationRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
 
    async def get_liquidation_by_id(self, liquidation_id: UUID) -> Optional[Liquidation]:
        try:
            result = await self.db.execute(
                select(LiquidationModel).where(LiquidationModel.id == liquidation_id)
            )
            model = result.scalars().first()
            if not model:
                raise NotFoundException("Liquidación no encontrada")
            
            return self.model_to_entity(model)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_liquidations(self) -> List[Liquidation]:
        try:
            result = await self.db.execute(select(LiquidationModel))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)        

    async def create_liquidation(self, liquidation: Liquidation) -> Optional[Liquidation]:
        orm_liquidation = self.entity_to_model(liquidation)
        self.db.add(orm_liquidation)
        try:
            await self.db.commit()
            await self.db.refresh(orm_liquidation)
            return self.model_to_entity(orm_liquidation)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_liquidation(self, liquidation: LiquidationUpdate) -> Optional[Liquidation]:
        try:
            result = await self.db.execute(
                select(LiquidationModel).where(LiquidationModel.id == liquidation.id)
            )
            current_liquidation = result.scalars().first()

            if not current_liquidation:
                raise NotFoundException("Liquidación no encontrada")

            update_data = liquidation.model_dump(exclude_unset=True)

            current_liquidation = self.update_values(update_data, current_model=current_liquidation)

            await self.db.commit()
            await self.db.refresh(current_liquidation)
            return self.model_to_entity(current_liquidation)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def delete_liquidation(self, liquidation_id:UUID):
        try:
            result = await self.db.execute(
                select(LiquidationModel).where(LiquidationModel.id == liquidation_id)
            )
            current_liquidation = result.scalars().first()

            if not current_liquidation:
                raise NotFoundException("La liquidación no fue encontrada")
            
            current_liquidation.active = False

            await self.db.commit()
            await self.db.refresh(current_liquidation)
            return "Liquidación eliminada exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            liquidation_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(liquidation_message)
