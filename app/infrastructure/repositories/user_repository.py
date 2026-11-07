from typing import List, Optional
from uuid import UUID
from sqlalchemy.future import select
from sqlalchemy.sql.expression import union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from ...presentation.shemas.user_shema import UserFilters
from app.domain.entities.user import User
from app.domain.repositories.user_repository import AbstractUserRepository
from app.infrastructure.models.user_model import UserModel
from app.infrastructure.models.models import UserType
from app.presentation.shemas.user_shema import UserUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException


class UserRepository(AbstractUserRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_queryset(self, filters: UserFilters):
        filtersDict = dict(filters)
        text = filtersDict.get('text', None)
        active = filtersDict.get('active', False) in ['True', True, 'true']
        
        if self.user.brand_id:
            stmt = select(UserModel).where(UserModel.brand_id == self.user.brand_id)
        else:
            stmt = select(UserModel)
        
        stmt = stmt.where(UserModel.active==active)

        if text:
            like = f"%{text}%"
            stmt = stmt.where(
                (UserModel.full_name.ilike(like))
                | (UserModel.document_id.ilike(like))
                | (UserModel.username.ilike(like))
                | (UserModel.email.ilike(like))
            )

        return stmt

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

    async def list_users(self, filters) -> List[User]:
        try:
            if not self.user:
                raise NotFoundException("Usuario no encontrado")

            query_stmt = await self.get_queryset(filters)

            result = await self.db.execute(query_stmt)
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
            if "type_user" in update_data:
                type_name = UserType.get_type(user_type=update_data["type_user"])
                update_data["type_user"] = UserType[type_name]

            for key, value in update_data.items():
                setattr(current_user, key, value)

            await self.db.commit()
            await self.db.refresh(current_user)
            return self.model_to_entity(current_user)
        
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def update_password(self, uuid: UUID, password: str) -> User:
        try:
            result = await self.db.execute(
                select(UserModel).where(UserModel.id == uuid)
            )

            current_user = result.scalars().first()

            if not current_user:
                raise NotFoundException("El usuario no fue encontrado")

            current_user.hashed_password = password

            await self.db.commit()
            await self.db.refresh(current_user)
            return self.model_to_entity(current_user)
        
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def get_by_clerk_id(self, clerk_user_id: str) -> Optional[User]:
        try:
            result = await self.db.execute(
                select(UserModel).where(UserModel.clerk_user_id == clerk_user_id)
            )
            model = result.scalars().first()
            if not model:
                return None
            return self.model_to_entity(model)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def set_clerk_user_id(self, user_id: UUID, clerk_user_id: str) -> User:
        try:
            result = await self.db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            current_user = result.scalars().first()
            if not current_user:
                raise NotFoundException("El usuario no fue encontrado")
            current_user.clerk_user_id = clerk_user_id
            await self.db.commit()
            await self.db.refresh(current_user)
            return self.model_to_entity(current_user)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def toggle_user(self, user_id:UUID):
        try:
            result = await self.db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            current_user = result.scalars().first()

            if not current_user:
                raise NotFoundException("El usuario no fue encontrado")
            
            current_user.active = False if current_user.active else True

            await self.db.commit()
            await self.db.refresh(current_user)
            return "Usuario modificado exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
