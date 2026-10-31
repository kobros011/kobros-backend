from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from app.domain.entities.user import User
from app.infrastructure.models.user_model import UserModel
from ...presentation.shemas.user_shema import UserFilters
from dataclasses import fields
from datetime import datetime


class AbstractUserRepository(ABC):
    user: Optional[UserModel] = None

    @abstractmethod
    async def get_queryset(self, filters: UserFilters):
        pass

    @abstractmethod
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        pass

    @abstractmethod
    async def list_users(self, filters: UserFilters) -> List[Optional[User]]:
        pass

    @abstractmethod
    async def create_user(self, user: User) -> User:
        pass

    @abstractmethod
    async def update_user(self, user: User) -> User:
        pass

    @abstractmethod
    async def update_password(self, uuid: UUID, password: str):
        pass

    @abstractmethod
    async def toggle_user(self, user_id: UUID):
        pass

    @abstractmethod
    async def get_by_clerk_id(self, clerk_user_id: str) -> Optional[User]:
        pass
    
    @staticmethod
    def model_to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            hashed_password=model.hashed_password,
            full_name=model.full_name,
            document_id=model.document_id,
            linking_date=model.linking_date,
            address=model.address,
            phone=model.phone,
            mobile=model.mobile,
            city=model.city,
            department=model.department,
            type_user=model.type_user,
            brand_id=model.brand_id,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            clerk_user_id=model.clerk_user_id,
        )

    @staticmethod
    def entity_to_model(entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            username=entity.username,
            email=entity.email,
            hashed_password=entity.hashed_password,
            full_name=entity.full_name,
            document_id=entity.document_id,
            linking_date=entity.linking_date,
            address=entity.address,
            phone=entity.phone,
            mobile=entity.mobile,
            city=entity.city,
            department=entity.department,
            type_user=entity.type_user,
            brand_id=entity.brand_id,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            clerk_user_id=entity.clerk_user_id,
        )
