from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from app.domain.entities.user import User
from app.infrastructure.models.user_model import UserModel


class AbstractUserRepository(ABC):
    @abstractmethod
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        pass

    @abstractmethod
    async def list_users(self) -> List[Optional[User]]:
        pass

    @abstractmethod
    async def create_user(self, user: User) -> User:
        pass

    @abstractmethod
    async def update_user(self, user: User) -> User:
        pass

    @abstractmethod
    async def delete_user(self, user_id: UUID):
        pass

    @staticmethod
    def model_to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            hashed_password=model.hashed_password,
            name=model.name,
            last_name=model.last_name,
            type_user=model.type_user,
            brand_id=model.brand_id,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def entity_to_model(entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            username=entity.username,
            hashed_password=entity.hashed_password,
            name=entity.name,
            last_name=entity.last_name,
            type_user=entity.type_user,
            brand_id=entity.brand_id,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
