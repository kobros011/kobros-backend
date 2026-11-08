from uuid import UUID
from ...domain.entities.route import Route
from ...domain.repositories.route_repository import AbstractRouteRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.route_model import RouteModel
from ..models.client_route_model import ClientRouteModel
from ...presentation.shemas.route_shema import RouteUpdate, RouteFilters
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException
from ..models.models import UserType
from ...core.pagination import PaginationParams, paginate_or_all

class RouteRepository(AbstractRouteRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_queryset(self, filters: RouteFilters):
        filtersDict = dict(filters)
        text = filtersDict.get('text', None)
        active = filtersDict.get('active', True) in ['True', True, 'true']


        if self.user.brand_id:
            stmt = select(RouteModel).where(RouteModel.brand_id == self.user.brand_id)
        else:
            stmt = select(RouteModel)
        
        stmt = stmt.where(RouteModel.active==active)

        if  self.user.type_user not in (UserType.super, UserType.dev):
            stmt = stmt.where(RouteModel.allowed_users_ids.contains([self.user.id]))

        if text:
            stmt = stmt.where((RouteModel.name.ilike(f"%{text}%")))

        return stmt
    
    async def get_route_by_id(self, route_id: UUID) -> Route:
        try:
            result = await self.db.execute(
                select(RouteModel).where(RouteModel.id == route_id)
            )

            model = result.scalars().first()
            if not model:
                raise NotFoundException("Ruta no encontrada")
            
            return self.model_to_entity(model)
        except IntegrityError as e:
            route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(route_message)
        
    async def get_latest_clientroute(self, route_id: UUID) -> ClientRouteModel | None:
        stmt = (
            select(ClientRouteModel)
            .where(ClientRouteModel.route_id == route_id)
            .order_by(ClientRouteModel.updated_at.desc())
            .limit(1)
        )

        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_routes(self, filters: RouteFilters, params: Optional[PaginationParams] = None) -> tuple[List[Route], int]:
        try:
            if not self.user:
                raise NotFoundException("Usuario no encontrado")

            query_stmt = (await self.get_queryset(filters)).order_by(RouteModel.name, RouteModel.id)
            return await paginate_or_all(self.db, query_stmt, params, self.model_to_entity)
        except IntegrityError as e:
            route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(route_message)

    async def create_route(self, route: Route) -> Optional[Route]:
        try:
            orm_route = self.entity_to_model(route)
            self.db.add(orm_route)
            await self.db.commit()
            await self.db.refresh(orm_route)
            return self.model_to_entity(orm_route)
        
        except IntegrityError as e:
            await self.db.rollback()
            route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(route_message)

    async def update_route(self, route: RouteUpdate) -> Optional[Route]:
        try:
            result = await self.db.execute(
                select(RouteModel).where(RouteModel.id == route.id)
            )
            current_route = result.scalars().first()

            if not current_route:
                raise NotFoundException("Ruta no encontrada")

            update_data = route.model_dump(exclude_unset=True)
            if update_data.get('currency') in (None, current_route.currency):
                update_data.pop('currency', None)

            current_route = self.update_values(update_data, current_model=current_route)

            await self.db.commit()
            await self.db.refresh(current_route)
            return self.model_to_entity(current_route)

        except IntegrityError as e:
            await self.db.rollback()
            route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(route_message)
        
    async def update_loan_number(self, route_id: UUID, new_loan_number: int):
        try:
            result = await self.db.execute(
                select(RouteModel).where(RouteModel.id == route_id)
            )
            current_route: RouteModel = result.scalars().first()

            if not current_route:
                raise NotFoundException("Ruta no encontrada")

            current_route.loans_number = new_loan_number

            await self.db.commit()
            await self.db.refresh(current_route)
            return self.model_to_entity(current_route)

        except IntegrityError as e:
            await self.db.rollback()
            route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(route_message)
        
    async def toggle_route(self, route_id:UUID):
        try:
            result = await self.db.execute(
                select(RouteModel).where(RouteModel.id == route_id)
            )
            current_route = result.scalars().first()

            if not current_route:
                raise NotFoundException("Ruta no encontrada")
            
            current_route.active = False if current_route.active else True

            await self.db.commit()
            await self.db.refresh(current_route)
            return "Ruta modificada exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(route_message)
