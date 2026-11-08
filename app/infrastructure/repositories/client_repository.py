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
from ..models.loan_model import LoanModel
from ..models.payment_model import PaymentModel
from sqlalchemy import func
from ..repositories.client_route_repository import ClientRouteRepository
from ..repositories.client_reference_repository import ClientReferenceRepository
from ...presentation.shemas.client_shema import ClientUpdate, ClientFilters, ClientCreate
from app.infrastructure.utils.validator_errors import ValidatorErrors
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.core.pagination import PaginationParams, paginate_or_all


class ClientRepository(AbstractClientRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def _attach_active_loans_count(self, clients: List[Client]) -> None:
        """Una sola consulta agrupada para los clientes de la página (evita N+1)."""
        ids = [c.id for c in clients if c.id]
        if not ids:
            return
        stmt = (
            select(ClientRouteModel.cliente_id, func.count(LoanModel.id))
            .join(LoanModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(ClientRouteModel.cliente_id.in_(ids))
            .where(LoanModel.active == True)
            .where(LoanModel.pending_quotas > 0)
            .group_by(ClientRouteModel.cliente_id)
        )
        rows = (await self.db.execute(stmt)).all()
        counts = {row[0]: row[1] for row in rows}
        for client in clients:
            client.active_loans_count = counts.get(client.id, 0)

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
            stmt = stmt.where(ClientModel.clientsroutes.any(ClientRouteModel.route_id.in_(routes_ids)))

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

            client = self.model_to_entity(model)
            await self._attach_route_totals([client])
            return client
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def _attach_route_totals(self, clients: List[Client]) -> None:
        """Agrega `route_total` (clientes activos de la ruta) a cada ruta de cada cliente, con una sola consulta."""
        route_ids = {item["route_id"] for client in clients for item in client.routes}
        if not route_ids:
            return
        stmt = (
            select(ClientRouteModel.route_id, func.count())
            .where(ClientRouteModel.route_id.in_(route_ids), ClientRouteModel.active.is_not(False))
            .group_by(ClientRouteModel.route_id)
        )
        totals = {route_id: count for route_id, count in (await self.db.execute(stmt)).all()}
        for client in clients:
            for item in client.routes:
                item["route_total"] = int(totals.get(item["route_id"], 0))

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

    async def list_clients(self, filters, params: Optional[PaginationParams] = None) -> tuple[List[Client], int]:
        try:
            if not self.user:
                raise NotFoundException("Usuario no encontrado")

            query_stmt = await self.get_queryset(filters)
            route_id = dict(filters).get("route_id", None)
            if route_id:  # con una ruta filtrada, primero por su prioridad en esa ruta
                priority = (
                    select(ClientRouteModel.order)
                    .where(ClientRouteModel.cliente_id == ClientModel.id, ClientRouteModel.route_id == route_id, ClientRouteModel.active.is_not(False))
                    .scalar_subquery()
                )
                query_stmt = query_stmt.order_by(priority, ClientModel.full_name, ClientModel.id)
            else:
                query_stmt = query_stmt.order_by(ClientModel.full_name, ClientModel.id)
            query_stmt = query_stmt.options(selectinload(ClientModel.clientsroutes), selectinload(ClientModel.references))
            items, total = await paginate_or_all(self.db, query_stmt, params, self.model_to_entity)
            await self._attach_active_loans_count(items)
            await self._attach_route_totals(items)
            return items, total
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def create_client(self, client: ClientCreate) -> Optional[Client]:

        async def create_routes_client(client_id: UUID):
            route_repo = ClientRouteRepository(self.db)
            for route_id in dict.fromkeys(client.routes_ids):
                await route_repo.create_order_client_route(cliente_id=client_id, route_id=route_id)
            
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
            routes_ids = client.routes_ids
            update_data = client.model_dump(exclude_unset=True, exclude={"references", "routes_ids"})

            current_client = self.update_values(update_data, current_model=current_client)

            if references is not None:
                ref_repo = ClientReferenceRepository(self.db)
                await ref_repo.replace_for_client(
                    current_client.id,
                    [r.model_dump() for r in references],
                )

            if routes_ids is not None:
                await self._sync_client_routes(current_client, routes_ids)

            await self.db.commit()
            await self.db.refresh(current_client, attribute_names=["clientsroutes", "references"])
            return self.model_to_entity(current_client)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def _sync_client_routes(self, client: ClientModel, routes_ids: List[UUID]) -> None:
        """Deja al cliente en exactamente `routes_ids`: agrega las nuevas (al final) y quita las que sobran
        (solo si no tienen créditos con cuotas pendientes). Solo administración."""
        desired = list(dict.fromkeys(routes_ids))
        if {cr.route_id for cr in client.clientsroutes if cr.active is not False} == set(desired):
            return  # el formulario reenvía las rutas actuales: sin cambios no hace falta ser administrador

        role = getattr(self.user.type_user, "value", str(self.user.type_user))
        if role in ("04", "05"):
            raise ForbiddenException("Solo un administrador puede cambiar las rutas de un cliente")

        if not desired:
            raise BadRequestException("El cliente debe tener al menos una ruta")
        valid = await self.db.execute(select(RouteModel.id).where(RouteModel.id.in_(desired), RouteModel.brand_id == client.brand_id))
        if len(valid.scalars().all()) != len(desired):
            raise NotFoundException("Alguna ruta no existe o es de otra marca")

        current = {cr.route_id: cr for cr in client.clientsroutes if cr.active is not False}
        to_remove = [route_id for route_id in current if route_id not in desired]
        route_repo = ClientRouteRepository(self.db)

        for route_id in to_remove:
            owed = await self.db.execute(
                select(func.count()).select_from(PaymentModel)
                .join(LoanModel, LoanModel.id == PaymentModel.loan_id)
                .where(
                    LoanModel.clientroute_id == current[route_id].id, LoanModel.active.is_not(False), PaymentModel.active.is_not(False),
                    PaymentModel.value - func.coalesce(PaymentModel.applied, 0) > 0.01,
                )
            )
            if owed.scalar_one():
                raise ConflictException("No puedes quitar una ruta en la que el cliente tiene créditos con saldo pendiente")
        for route_id in to_remove:
            current[route_id].active = False
        await self.db.flush()
        for route_id in to_remove:
            await route_repo.compact_route(route_id)
        for route_id in desired:
            if route_id not in current:
                await route_repo.create_order_client_route(cliente_id=client.id, route_id=route_id)

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
