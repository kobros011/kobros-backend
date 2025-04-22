from uuid import UUID
from ...domain.entities.client import Client
from ...domain.repositories.client_repository import AbstractClientRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.client_model import ClientModel
from ...presentation.shemas.client_shema import ClientUpdate
from app.infrastructure.utils.validator_errors import ValidatorErrors
from app.core.exceptions import ConflictException, NotFoundException


class ClientRepository(AbstractClientRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
 
    async def get_client_by_id(self, client_id: UUID) -> Optional[Client]:
        try:
            result = await self.db.execute(
                select(ClientModel).where(ClientModel.id == client_id)
            )
            model = result.scalars().first()
            if not model:
                raise NotFoundException("El cliente no fue encontrado")
            return self.model_to_entity(model)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_clients(self) -> List[Client]:
        try:
                
            result = await self.db.execute(select(ClientModel))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def create_client(self, client: Client) -> Optional[Client]:
        orm_client = self.entity_to_model(client)
        self.db.add(orm_client)
        try:
            await self.db.commit()
            await self.db.refresh(orm_client)
            return self.model_to_entity(orm_client)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_client(self, client: ClientUpdate) -> Optional[Client]:
        try:
            result = await self.db.execute(
                select(ClientModel).where(ClientModel.id == client.id)
            )
            current_client = result.scalars().first()

            if not current_client:
                raise NotFoundException("El cliente no fue encontrado")

            update_data = client.model_dump(exclude_unset=True)

            current_client = self.update_values(update_data, current_model=current_client)

            await self.db.commit()
            await self.db.refresh(current_client)
            return self.model_to_entity(current_client)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def delete_client(self, client_id:UUID):
        try:
            result = await self.db.execute(
                select(ClientModel).where(ClientModel.id == client_id)
            )
            current_client = result.scalars().first()

            if not current_client:
                raise NotFoundException("El cliente no fue encontrado")
            
            current_client.active = False

            await self.db.commit()
            await self.db.refresh(current_client)
            return "Client eliminado exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            client_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(client_message)
