from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.brand import Brand
from typing import Optional, List
from app.infrastructure.models.brand_model import BrandModel
from app.infrastructure.models.user_model import UserModel

class AbstractBrandRepository(ABC):
    user: Optional[UserModel] = None
    @abstractmethod
    async def get_brand_by_id(self, brand_id: UUID) -> Optional[Brand]:
        pass

    @abstractmethod
    async def list_brands(self, filters) -> List[Brand]:
        pass

    @abstractmethod
    async def create_brand(self, brand: Brand) -> Optional[Brand]:
        pass

    @abstractmethod
    async def update_brand(self, brand: Brand) -> Optional[Brand]:
        pass

    @abstractmethod
    async def toggle_brand(self, brand_id: UUID):
        pass


    @staticmethod
    def model_to_entity(model: BrandModel) -> Brand:
        return Brand(
            id=model.id,
            code=model.code,
            routes_available=model.routes_available,
            name=model.name,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def entity_to_model(entity: Brand) -> BrandModel:
        return BrandModel(
            id=entity.id,
            code=entity.code,
            routes_available=entity.routes_available,
            name=entity.name,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
    
    @staticmethod
    def update_values(update_data: dict[str, any], current_model:BrandModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)
        

        return current_model
