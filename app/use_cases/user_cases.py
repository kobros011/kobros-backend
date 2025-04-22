from typing import List, Optional
from uuid import UUID
from app.domain.entities.user import User
from app.domain.repositories.user_repository import AbstractUserRepository
from app.core.auth import get_password_hash
from app.presentation.shemas.user_shema import UserCreate, UserUpdate
from app.infrastructure.models.user_model import UserType


class UserUseCases:
    def __init__(self, repository: AbstractUserRepository):
        self.repository = repository

    async def get_user(self, user_id: UUID) -> Optional[User]:
        return await self.repository.get_user_by_id(user_id)

    async def list_users(self) -> List[Optional[User]]:
        return await self.repository.list_users()

    async def create_user(self, user: UserCreate) -> User:
        user_data = user.model_dump(exclude=["password"])
        user_data["type_user"] = UserType.get_type(user_type=user.type_user)

        new_user = User(**user_data, hashed_password=get_password_hash(user.password))
        return await self.repository.create_user(new_user)

    async def update_user(self, user=UserUpdate) -> User:
        return await self.repository.update_user(user)

    async def delete_user(self, user_id: UUID):
        return await self.repository.delete_user(user_id)