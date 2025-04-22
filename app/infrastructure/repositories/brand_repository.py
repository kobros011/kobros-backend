from uuid import UUID
from ...domain.entities.brand import Brand
from ...domain.repositories.brand_repository import AbstractBrandRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.brand_model import BrandModel
from ...presentation.shemas.brand_shema import BrandUpdate
from app.infrastructure.utils.validator_errors import ValidatorErrors
from app.core.exceptions import ConflictException, NotFoundException

class BrandRepository(AbstractBrandRepository):
    def __init__(self, db:AsyncSession):
        self.db = db

    async def get_brand_by_id(self, brand_id: UUID) -> Optional[Brand]:
        try:
            result = await self.db.execute(select(BrandModel).where(BrandModel.id == brand_id))
            model = result.scalars().first()

            if not model:
                raise NotFoundException("La marca no fue encontrada")
            return self.model_to_entity(model)
        
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_brands(self) -> List[Brand]:
        try:
            result = await self.db.execute(select(BrandModel))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    
    async def create_brand(self, brand: Brand) -> Optional[Brand]:
        orm_brand = self.entity_to_model(brand)
        self.db.add(orm_brand)
        try: 
            await self.db.commit()
            await self.db.refresh(orm_brand)
            return self.model_to_entity(orm_brand)
        
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

        
    async def update_brand(self, brand: BrandUpdate) -> Optional[Brand]:
        try: 
            result = await self.db.execute(select(BrandModel).where(BrandModel.id == brand.id))
            current_brand = result.scalars().first()
            
            if not current_brand:
                raise ValueError("Marca no encontrada")

            update_data = brand.model_dump(exclude_unset=True)
            
            current_brand = self.update_values(update_data, current_model=current_brand)

            await self.db.commit()
            await self.db.refresh(current_brand)
            return self.model_to_entity(current_brand)
        
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def delete_brand(self, brand_id:UUID):
        try:
            result = await self.db.execute(
                select(BrandModel).where(BrandModel.id == brand_id)
            )
            current_brand = result.scalars().first()

            if not current_brand:
                raise NotFoundException("La marca no fue encontrada")
            
            current_brand.active = False

            await self.db.commit()
            await self.db.refresh(current_brand)
            return "Marca eliminada exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            brand_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(brand_message)