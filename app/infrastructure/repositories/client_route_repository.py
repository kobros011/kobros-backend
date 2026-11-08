from uuid import UUID
from ...domain.entities.client_route import ClientRoute
from ...domain.repositories.client_route_repository import AbstractClientRouteRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy import bindparam, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.client_route_model import ClientRouteModel
from ...presentation.shemas.client_route_shema import ClientRouteUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import BadRequestException, ConflictException, NotFoundException
from ..models.route_model import RouteModel
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
                select(ClientRouteModel).where(ClientRouteModel.route_id == route_id, ClientRouteModel.active.is_not(False))
                .options(selectinload(ClientRouteModel.client))
                .order_by(ClientRouteModel.order, ClientRouteModel.created_at, ClientRouteModel.id)
                .execution_options(populate_existing=True)
            )
            result = await self.db.execute(stmt)
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def _next_order(self, route_id) -> int:
        """Siguiente prioridad de la ruta: máximo actual + 1 (solo filas activas)."""
        current = await self.db.execute(
            select(func.coalesce(func.max(ClientRouteModel.order), 0)).where(ClientRouteModel.route_id == route_id, ClientRouteModel.active.is_not(False))
        )
        return int(current.scalar_one()) + 1

    async def create_order_client_route(self, cliente_id, route_id):
        found = await self.db.execute(
            select(ClientRouteModel).where(ClientRouteModel.route_id == route_id, ClientRouteModel.cliente_id == cliente_id)
            .order_by(ClientRouteModel.active.desc().nulls_last(), ClientRouteModel.created_at).limit(1)
        )
        existing = found.scalars().first()

        if existing and existing.active is not False:
            return existing

        try:
            if existing:  # estaba inactivo: se reactiva al final de la ruta
                next_order = await self._next_order(route_id)
                existing.active = True
                existing.order = next_order
                await self.db.commit()
                await self.db.refresh(existing)
                return existing

            orm_client_route = ClientRouteModel(cliente_id=cliente_id, route_id=route_id, order=await self._next_order(route_id))
            self.db.add(orm_client_route)
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

    async def update_multiples_orders(self, current_client_route_id: UUID, new_order: int, commit: bool = True):
        try:
            current_client_route = await self.db.execute(select(ClientRouteModel).where(ClientRouteModel.id == current_client_route_id))
            current_client_route = current_client_route.scalars().first()

            if not current_client_route:
                raise NotFoundException("Orden del cliente no encontrado")
            
            max_order_route = await self.db.execute(select(func.count()).where(ClientRouteModel.route_id == current_client_route.route_id, ClientRouteModel.active.is_not(False)))
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
                    ClientRouteModel.active.is_not(False),
                    ClientRouteModel.id != current_client_route_id,
                    ClientRouteModel.order >= new_order,
                    ClientRouteModel.order < old_order
                ).values(order=ClientRouteModel.order + 1))
            else:
                await self.db.execute(
                update(ClientRouteModel)
                .where(
                    ClientRouteModel.route_id == current_client_route.route_id,
                    ClientRouteModel.active.is_not(False),
                    ClientRouteModel.id != current_client_route_id,
                    ClientRouteModel.order <= new_order,
                    ClientRouteModel.order > old_order
                ).values(order=ClientRouteModel.order -  1))

            current_client_route.order = new_order

            if commit:
                await self.db.commit()
            return current_client_route
        except IntegrityError as e:
            await self.db.rollback()
            client_route_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(client_route_message) 

    # ---- reordenamiento de una ruta (prioridades 1..n sin repetidos ni huecos) ----
    async def _lock_active_rows(self, route_id: UUID) -> list[ClientRouteModel]:
        """Bloquea la ruta (serializa reordenamientos simultáneos) y devuelve sus filas activas por prioridad."""
        locked = await self.db.execute(select(RouteModel.id).where(RouteModel.id == route_id).with_for_update())
        if locked.scalar_one_or_none() is None:
            raise NotFoundException("Ruta no encontrada")
        rows = await self.db.execute(
            select(ClientRouteModel)
            .where(ClientRouteModel.route_id == route_id, ClientRouteModel.active.is_not(False))
            .order_by(ClientRouteModel.order, ClientRouteModel.created_at, ClientRouteModel.id)
            .execution_options(populate_existing=True)
        )
        return list(rows.scalars().all())

    async def _apply_order(self, ordered_ids: list[UUID]) -> None:
        if not ordered_ids:
            return
        table = ClientRouteModel.__table__  # UPDATE de Core (executemany): el modo ORM exige la clave primaria en cada fila
        await self.db.execute(
            update(table).where(table.c.id == bindparam("b_id")).values(order=bindparam("b_order")),
            [{"b_id": cr_id, "b_order": position} for position, cr_id in enumerate(ordered_ids, start=1)],
        )

    async def reorder_route(self, route_id: UUID, ordered_ids: list[UUID]) -> List[ClientRoute]:
        """Fija el orden completo de la ruta. `ordered_ids` debe traer exactamente sus clientes activos."""
        try:
            rows = await self._lock_active_rows(route_id)
            if set(ordered_ids) != {r.id for r in rows} or len(ordered_ids) != len(rows):
                raise ConflictException("La ruta cambió mientras la ordenabas. Actualiza la lista e inténtalo de nuevo")
            await self._apply_order(list(ordered_ids))
            await self.db.commit()
            return await self.list_client_routes(route_id)
        except IntegrityError as e:
            await self.db.rollback()
            raise ConflictException(ValidatorErrors.integrity_error(e))

    async def bulk_move(self, route_id: UUID, client_route_ids: list[UUID], target: str, position: Optional[int] = None) -> List[ClientRoute]:
        """Mueve varios clientes de la ruta al inicio, al final o a una posición, conservando su orden relativo."""
        try:
            rows = await self._lock_active_rows(route_id)
            by_id = {r.id for r in rows}
            if any(cr not in by_id for cr in client_route_ids):
                raise BadRequestException("Algún cliente no pertenece a esta ruta o está inactivo")
            chosen = set(client_route_ids)
            moved = [r.id for r in rows if r.id in chosen]          # conserva el orden relativo actual
            rest = [r.id for r in rows if r.id not in chosen]
            if target == "start":
                result = moved + rest
            elif target == "end":
                result = rest + moved
            elif target == "position":
                if not position or position < 1:
                    raise BadRequestException("La posición debe ser 1 o mayor")
                index = min(position - 1, len(rest))
                result = rest[:index] + moved + rest[index:]
            else:
                raise BadRequestException("Destino no válido")
            await self._apply_order(result)
            await self.db.commit()
            return await self.list_client_routes(route_id)
        except IntegrityError as e:
            await self.db.rollback()
            raise ConflictException(ValidatorErrors.integrity_error(e))

    async def move_client_route(self, client_route_id: UUID, position: int) -> List[ClientRoute]:
        """Mueve un cliente a `position` dentro de su ruta; los demás se recorren."""
        found = await self.db.execute(select(ClientRouteModel.route_id).where(ClientRouteModel.id == client_route_id))
        route_id = found.scalar_one_or_none()
        if route_id is None:
            raise NotFoundException("Orden del cliente no encontrado")
        return await self.bulk_move(route_id, [client_route_id], "position", position)

    async def compact_route(self, route_id: UUID) -> None:
        """Renumera 1..n las prioridades activas de la ruta (sin commit; lo hace quien llama)."""
        rows = await self._lock_active_rows(route_id)
        await self._apply_order([r.id for r in rows])
