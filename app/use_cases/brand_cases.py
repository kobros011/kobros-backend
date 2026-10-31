from uuid import UUID
from typing import Optional, List
from ..domain.repositories.brand_repository import AbstractBrandRepository
from ..domain.entities.brand import Brand
from ..presentation.shemas.brand_shema import BrandCreate, BrandUpdate, BrandFilters
from app.infrastructure.models.user_model import UserModel

class BrandUseCases:
    user: Optional[UserModel] = None
    def __init__(self, repository: AbstractBrandRepository):
        self.repository = repository

    async def get_brand(self, brand_id: UUID) -> Optional[Brand]:
        return await self.repository.get_brand_by_id(brand_id)
    
    async def list_brands(self, filters: BrandFilters) -> List[Brand]:
        return await self.repository.list_brands(filters)
    
    async def create_brand(self, brand: BrandCreate) -> Optional[Brand]:
        new_brand = Brand(**brand.model_dump())
        return await self.repository.create_brand(new_brand)
    
    async def update_brand(self, brand: BrandUpdate) -> Optional[Brand]:
        return await self.repository.update_brand(brand)
    
    async def toggle_brand(self, brand_id: UUID):
        return await self.repository.toggle_brand(brand_id)
