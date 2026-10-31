from uuid import UUID

from ...domain.entities.client import ClientById
from ...domain.entities.client import Client
from ...domain.repositories.client_repository import AbstractClientRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List
from ..models.client_model import ClientModel
from ..models.client_reference_model import ClientReferenceModel
from ..models.route_model import RouteModel
from ..models.client_route_model import ClientRouteModel
from ..repositories.client_route_repository import ClientRouteRepository
from ..repositories.client_reference_repository import ClientReferenceRepository
from ...presentation.shemas.client_shema import ClientUpdate, ClientFilters, ClientCreate
from app.infrastructure.utils.validator_errors import ValidatorErrors
from app.core.exceptions import ConflictException, NotFoundException


class ClientRepository(AbstractClientRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_routes_id(self):
        routes = await self.db.execute(select(RouteModel.id).where(RouteModel.allowed_users_ids.contains([self.user.id])))
        routes_ids = [row[0] for row in routes.all()]
        return routes_ids

    async def get_queryset(self, filters: ClientFilters):
        filtersDict = dict(filters)
        text = filtersDict.get('text', None)
        route_id = filtersDict.get('route_id', None)
        active = filtersDict.get('active', True) in ['True', True, 'true']

        routes_ids = [route_id] if route_id else await self.get_routes_id()

        if self.user.brand_id:
            stmt = select(ClientModel).where(ClientModel.brand_id == self.user.brand_id)
        else:
            stmt = select(ClientModel)

        stmt = stmt.where(ClientModel.active==active)

        if len(routes_ids):
            stmt = stmt.join(ClientModel.clientsroutes)
            stmt = stmt.where(ClientRouteModel.route_id.in_(routes_ids))
            stmt = stmt.distinct(ClientModel.id)

        if text:
            stmt = stmt.where((ClientModel.full_name.ilike(f"%{text}%")) | (ClientModel.id_document.ilike(f"%{text}%")))

        return stmt

    async def get_client_by_id(self, client_id: UUID) -> Optional[Client]:
        try:
            result = await self.db.execute(
                select(ClientModel).where(ClientModel.id == client_id)
                .options(selectinload(ClientModel.clientsroutes), selectinload(ClientModel.references))
            )
            model = result.scalars().first()
            if not model:
                raise NotFoundException("El cliente no fue encontrado")

            return self.model_to_entity(model)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def get_by_id_more_info(self, client_id: UUID, route_id: UUID) -> ClientById | None:
        try:
            result = await self.db.execute(
                select(ClientModel).where(ClientModel.id == client_id)
                .options(
                    selectinload(ClientModel.clientsroutes)
                    .selectinload(ClientRouteModel.route),
                    selectinload(ClientModel.references),
                )
            )

            model = result.scalar_one()
            if not model:
                raise NotFoundException("El cliente no fue encontrado")
            
            return self.model_by_id_to_entity(model=model, route_id=route_id)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_clients(self, filters) -> List[Client]:
        try:
            if not self.user:
                raise NotFoundException("Usuario no encontrado")
            
            
            query_stmt = await self.get_queryset(filters)
            query_stmt = query_stmt.options(selectinload(ClientModel.clientsroutes), selectinload(ClientModel.references))
            result = await self.db.execute(query_stmt)

            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def create_client(self, client: ClientCreate) -> Optional[Client]:

        async def create_routes_client(client_id: UUID):
            for route_id in client.routes_ids:
                clint_route = await ClientRouteRepository.create_order_client_route(self=self, cliente_id=client_id, route_id=route_id)
                return clint_route
            
        try:
            stmt = (
                select(ClientModel)
                .where(ClientModel.brand_id == self.user.brand_id)
                .where(
                    (ClientModel.full_name.ilike(f"%{client.full_name}%")) |
                    (ClientModel.id_document.ilike(f"%{client.id_document}%"))
                )
                .limit(1)
            )
            exists_client = await self.db.execute(stmt)
            exists_client = exists_client.scalars().first()

            ref_repo = ClientReferenceRepository(self.db)

            if not exists_client:
                    orm_client = self.entity_to_model(Client(**client.model_dump(exclude=["routes_ids", "references"])))
                    orm_client.guarantor_name = client.guarantor_name
                    orm_client.guarantor_cedula = client.guarantor_cedula
                    orm_client.guarantor_phone = client.guarantor_phone
                    orm_client.guarantor_address = client.guarantor_address
                    self.db.add(orm_client)
                    await self.db.flush()

                    await create_routes_client(orm_client.id)

                    if client.references:
                        await ref_repo.replace_for_client(
                            orm_client.id,
                            [r.model_dump() for r in client.references],
                        )

                    await self.db.commit()
                    await self.db.refresh(orm_client, attribute_names=["clientsroutes", "references"])

                    return self.model_to_entity(orm_client)

            if not exists_client.active:
                await self.toggle_client(client_id=exists_client.id)

            await create_routes_client(client_id=exists_client.id)

            return exists_client

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_client(self, client: ClientUpdate) -> Optional[Client]:
        try:
            result = await self.db.execute(
                select(ClientModel).where(ClientModel.id == client.id)
                .options(selectinload(ClientModel.clientsroutes), selectinload(ClientModel.references))
            )
            current_client = result.scalars().first()

            if not current_client:
                raise NotFoundException("El cliente no fue encontrado")

            references = client.references
            update_data = client.model_dump(exclude_unset=True, exclude={"references"})

            current_client = self.update_values(update_data, current_model=current_client)

            if references is not None:
                ref_repo = ClientReferenceRepository(self.db)
                await ref_repo.replace_for_client(
                    current_client.id,
                    [r.model_dump() for r in references],
                )

            await self.db.commit()
            await self.db.refresh(current_client, attribute_names=["clientsroutes", "references"])
            return self.model_to_entity(current_client)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def toggle_client(self, client_id:UUID):
        try:
            result = await self.db.execute(
                select(ClientModel).where(ClientModel.id == client_id)
            )
            current_client = result.scalars().first()

            if not current_client:
                raise NotFoundException("El cliente no fue encontrado")
            
            current_client.active = False if current_client.active else True

            await self.db.commit()
            await self.db.refresh(current_client)
            return "Client eliminado exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            client_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(client_message)
