from uuid import UUID
from typing import Optional, List
from ..domain.repositories.brand_repository import AbstractBrandRepository
from ..domain.entities.brand import Brand
from ..presentation.shemas.brand_shema import BrandCreate, BrandUpdate

class BrandUseCases:
    def __init__(self, repository: AbstractBrandRepository):
        self.repository = repository

    async def get_brand(self, brand_id: UUID) -> Optional[Brand]:
        return await self.repository.get_brand_by_id(brand_id)
    
    async def list_brands(self) -> List[Brand]:
        return await self.repository.list_brands()
    
    async def create_brand(self, brand: BrandCreate) -> Optional[Brand]:
        new_brand = Brand(**brand.model_dump())
        return await self.repository.create_brand(new_brand)
    
    async def update_brand(self, brand: BrandUpdate) -> Optional[Brand]:
        return await self.repository.update_brand(brand)
    
    async def delete_brand(self, brand_id: UUID):
        return await self.repository.delete_brand(brand_id)
