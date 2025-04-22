from uuid import UUID
from ...domain.entities.client_route import ClientRoute
from ...domain.repositories.client_route_repository import AbstractClientRouteRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.client_route_model import ClientRouteModel
from ...presentation.shemas.client_route_shema import ClientRouteUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException


class ClientRouteRepository(AbstractClientRouteRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
 
    async def get_client_route_by_id(self, client_route_id: UUID) -> Optional[ClientRoute]:
        try:
            result = await self.db.execute(
                select(ClientRouteModel).where(ClientRouteModel.id == client_route_id)
            )
            model = result.scalars().first()
            if not model:
                raise NotFoundException("Orden del cliente no encontrado")
            
            return self.model_to_entity(model) if model else None
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_client_routes(self) -> List[ClientRoute]:
        try:
            result = await self.db.execute(select(ClientRouteModel))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_client_route(self, client_route: ClientRoute) -> Optional[ClientRoute]:
        orm_client_route = self.entity_to_model(client_route)
        self.db.add(orm_client_route)
        try:
            await self.db.commit()
            await self.db.refresh(orm_client_route)
            return self.model_to_entity(orm_client_route)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_client_route(self, client_route: ClientRouteUpdate) -> Optional[ClientRoute]:
        try:
            result = await self.db.execute(
                select(ClientRouteModel).where(ClientRouteModel.id == client_route.id)
            )
            current_client_route = result.scalars().first()

            if not current_client_route:
                raise NotFoundException("Orden del cliente no encontrado")

            update_data = client_route.model_dump(exclude_unset=True)

            current_client_route = self.update_values(update_data, current_model=current_client_route)

            await self.db.commit()
            await self.db.refresh(current_client_route)
            return self.model_to_entity(current_client_route)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def delete_client_route(self, client_route_id:UUID):
        try:
            result = await self.db.execute(
                select(ClientRouteModel).where(ClientRouteModel.id == client_route_id)
            )
            current_client_route = result.scalars().first()

            if not current_client_route:
                raise NotFoundException("Orden del cliente no encontrado")
            
            current_client_route.active = False

            await self.db.commit()
            await self.db.refresh(current_client_route)
            return "Orden del cliente eliminado exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            client_route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(client_route_message)
