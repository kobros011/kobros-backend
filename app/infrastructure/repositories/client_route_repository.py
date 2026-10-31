from uuid import UUID
from ...domain.entities.client_route import ClientRoute
from ...domain.repositories.client_route_repository import AbstractClientRouteRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.client_route_model import ClientRouteModel
from ...presentation.shemas.client_route_shema import ClientRouteUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException
from ..repositories.route_repository import RouteRepository
from sqlalchemy.orm import selectinload


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

    async def list_client_routes(self, route_id: Optional[UUID]) -> List[ClientRoute]:
        try:
            stmt = (
                select(ClientRouteModel).where(ClientRouteModel.route_id == route_id)
                .options(selectinload(ClientRouteModel.client))
            )
            result = await self.db.execute(stmt)
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_order_client_route(self, cliente_id, route_id):
        exist_route_cliente = await self.db.execute(select(ClientRouteModel).where(ClientRouteModel.route_id == route_id, ClientRouteModel.cliente_id == cliente_id).limit(1))
        exist_route_cliente = exist_route_cliente.scalars().first()

        if exist_route_cliente:
            return exist_route_cliente

        last_route_cliente: ClientRouteModel = await RouteRepository.get_latest_clientroute(self=self, route_id=route_id)
        
        orm_client_route = ClientRoute(client_id=cliente_id, route_id=route_id, order=last_route_cliente.order + 1 if last_route_cliente else 1)
        orm_client_route = AbstractClientRouteRepository.entity_to_model(orm_client_route)

        self.db.add(orm_client_route)

        try:
            await self.db.commit()
            await self.db.refresh(orm_client_route)
            return orm_client_route
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)


    async def create_client_route(self, client_route: ClientRoute) -> Optional[ClientRoute]:
        orm_client_route = self.entity_to_model(client_route)
        self.db.add(orm_client_route)
        try:
            await self.db.commit()
            result = await self.db.execute(
                select(ClientRouteModel)
                .where(ClientRouteModel.id == orm_client_route.id)
                .options(selectinload(ClientRouteModel.client))
            )
            orm_client_route = result.scalars().first()
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

    async def update_multiples_orders(self, current_client_route_id: UUID, new_order: int):
        try:
            current_client_route = await self.db.execute(select(ClientRouteModel).where(ClientRouteModel.id == current_client_route_id))
            current_client_route = current_client_route.scalars().first()

            if not current_client_route:
                raise NotFoundException("Orden del cliente no encontrado")
            
            max_order_route = await self.db.execute(select(func.count()).where((ClientRouteModel.route_id == current_client_route.route_id)))
            max_order_route = max_order_route.scalar_one()

            new_order = max(1, min(new_order, max_order_route))
            old_order = current_client_route.order

            if new_order == old_order:
                return
            
            if new_order < old_order:
                await self.db.execute(
                update(ClientRouteModel)
                .where(
                    ClientRouteModel.route_id == current_client_route.route_id,
                    ClientRouteModel.id != current_client_route_id,
                    ClientRouteModel.order >= new_order,
                    ClientRouteModel.order < old_order
                ).values(order=ClientRouteModel.order + 1))
            else:
                await self.db.execute(
                update(ClientRouteModel)
                .where(
                    ClientRouteModel.route_id == current_client_route.route_id,
                    ClientRouteModel.id != current_client_route_id,
                    ClientRouteModel.order <= new_order,
                    ClientRouteModel.order > old_order
                ).values(order=ClientRouteModel.order -  1))

            current_client_route.order = new_order

            await self.db.commit()
            return current_client_route
        except IntegrityError as e:
            await self.db.rollback()
            client_route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(client_route_message) 