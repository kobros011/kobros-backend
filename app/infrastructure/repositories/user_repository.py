from typing import List, Optional
from uuid import UUID
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.domain.entities.user import User
from app.domain.repositories.user_repository import AbstractUserRepository
from app.infrastructure.models.user_model import UserModel, UserType
from app.presentation.shemas.user_shema import UserUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException


class UserRepository(AbstractUserRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        try:
            result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
            model = result.scalars().first()

            if not model:
                raise NotFoundException("El usuario no fue encontrado")

            return self.model_to_entity(model)
            
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_users(self) -> List[User]:
        try:
            result = await self.db.execute(select(UserModel))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_user(self, user: User) -> User:
        orm_user = self.entity_to_model(user)
        self.db.add(orm_user)

        try:
            await self.db.commit()
            await self.db.refresh(orm_user)
            return self.model_to_entity(orm_user)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_user(self, user: UserUpdate) -> User:
        try:
            result = await self.db.execute(
                select(UserModel).where(UserModel.id == user.id)
            )
            current_user = result.scalars().first()

            if not current_user:
                raise NotFoundException("El usuario no fue encontrado")

            update_data = user.model_dump(exclude_unset=True)
            update_data["type_user"] = UserType.get_type(user_type=user.type_user)

            for key, value in update_data.items():
                setattr(current_user, key, value)

            await self.db.commit()
            await self.db.refresh(current_user)
            return self.model_to_entity(current_user)
        
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def delete_user(self, user_id:UUID):
        try:
            result = await self.db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            current_user = result.scalars().first()

            if not current_user:
                raise NotFoundException("El usuario no fue encontrado")
            
            current_user.active = False

            await self.db.commit()
            await self.db.refresh(current_user)
            return "Usuario eliminado exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
