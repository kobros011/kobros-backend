from uuid import UUID
from ...domain.entities.route import Route
from ...domain.repositories.route_repository import AbstractRouteRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.route_model import RouteModel
from ...presentation.shemas.route_shema import RouteUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException

class RouteRepository(AbstractRouteRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_route_by_id(self, route_id: UUID) -> Optional[Route]:
        try:
            result = await self.db.execute(
                select(RouteModel).where(RouteModel.id == route_id)
            )
            if not model:
                raise NotFoundException("Ruta no encontrada")
            
            model = result.scalars().first()
            return self.model_to_entity(model)
        except IntegrityError as e:
            route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(route_message)

    async def list_routes(self) -> List[Route]:
        try:
            result = await self.db.execute(select(RouteModel))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
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

            current_route = self.update_values(update_data, current_model=current_route)

            await self.db.commit()
            await self.db.refresh(current_route)
            return self.model_to_entity(current_route)

        except IntegrityError as e:
            await self.db.rollback()
            route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(route_message)
        
    async def delete_route(self, route_id:UUID):
        try:
            result = await self.db.execute(
                select(RouteModel).where(RouteModel.id == route_id)
            )
            current_route = result.scalars().first()

            if not current_route:
                raise NotFoundException("Ruta no encontrada")
            
            current_route.active = False

            await self.db.commit()
            await self.db.refresh(current_route)
            return "Ruta eliminada exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(route_message)
