"""Rutas de un usuario (admin, socio o cobrador): ver a cuáles pertenece, asignarlo y quitarlo.

La asignación vive en `routes.allowed_users_ids`; aquí se agrega o quita **un** usuario con una sola sentencia
(`array_append` / `array_remove`) para no pisar cambios concurrentes de otros usuarios en esa misma ruta.
"""
from uuid import UUID

from sqlalchemy import func, literal, select, update
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.infrastructure.models.client_route_model import ClientRouteModel
from app.infrastructure.models.liquidation_model import LiquidationModel
from app.infrastructure.models.loan_model import LoanModel
from app.infrastructure.models.payment_model import PaymentModel
from app.infrastructure.models.route_model import RouteModel
from app.infrastructure.models.user_model import UserModel
from app.infrastructure.utils.route_users import ASSIGNABLE_ROLES


def role_of(user: UserModel) -> str:
    return user.type_user.value if hasattr(user.type_user, "value") else str(user.type_user)


class UserRouteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_target(self, actor: UserModel, user_id: UUID, *, must_be_active: bool) -> UserModel:
        """Usuario a asignar: de la marca del actor (el dev, de cualquiera) y de un rol que se asigna por ruta."""
        target = await self.db.get(UserModel, user_id)
        if target is None or (actor.brand_id and target.brand_id != actor.brand_id):
            raise NotFoundException("Usuario no encontrado")
        if role_of(target) not in ASSIGNABLE_ROLES:
            raise BadRequestException("Este usuario ve todas las rutas de su marca")
        if must_be_active and not target.active:
            raise BadRequestException("El usuario está inactivo")
        return target

    async def _route_of_user_brand(self, user: UserModel, route_id: UUID) -> RouteModel:
        route = await self.db.get(RouteModel, route_id)
        if route is None or route.brand_id != user.brand_id:
            raise NotFoundException("Ruta no encontrada")
        return route

    async def _pending(self, user_id: UUID, route_ids: list[UUID]) -> dict[UUID, tuple[int, int]]:
        """Por ruta: (cobros del usuario sin liquidar, cierres del usuario sin confirmar)."""
        if not route_ids:
            return {}
        payments = (await self.db.execute(
            select(ClientRouteModel.route_id, func.count(PaymentModel.id))
            .select_from(PaymentModel)
            .join(LoanModel, LoanModel.id == PaymentModel.loan_id)
            .join(ClientRouteModel, ClientRouteModel.id == LoanModel.clientroute_id)
            .where(PaymentModel.collected_by == user_id, PaymentModel.liquidation_id.is_(None), PaymentModel.applied > 0, ClientRouteModel.route_id.in_(route_ids))
            .group_by(ClientRouteModel.route_id)
        )).all()
        liquidations = (await self.db.execute(
            select(LiquidationModel.route_id, func.count(LiquidationModel.id))
            .where(LiquidationModel.collector_id == user_id, LiquidationModel.route_id.in_(route_ids), LiquidationModel.admin_confirmed_at.is_(None),
                   LiquidationModel.reopened_at.is_(None), LiquidationModel.active.is_(True))
            .group_by(LiquidationModel.route_id)
        )).all()
        counts = {route_id: [count, 0] for route_id, count in payments}
        for route_id, count in liquidations:
            counts.setdefault(route_id, [0, 0])[1] = count
        return {route_id: (pay, liq) for route_id, (pay, liq) in counts.items()}

    async def list_for_user(self, actor: UserModel, user_id: UUID) -> list[dict]:
        target = await self.get_target(actor, user_id, must_be_active=False)
        routes = (await self.db.execute(select(RouteModel).where(RouteModel.brand_id == target.brand_id).order_by(RouteModel.name))).scalars().all()
        assigned = [route.id for route in routes if target.id in (route.allowed_users_ids or [])]
        pending = await self._pending(target.id, assigned)
        return [
            {
                "route_id": route.id, "name": route.name, "currency": route.currency, "active": route.active is not False,
                "assigned": route.id in assigned,
                "pending_payments": pending.get(route.id, (0, 0))[0], "open_liquidations": pending.get(route.id, (0, 0))[1],
            }
            for route in routes
        ]

    async def assign(self, actor: UserModel, user_id: UUID, route_id: UUID) -> None:
        target = await self.get_target(actor, user_id, must_be_active=True)
        await self._route_of_user_brand(target, route_id)
        uid = literal(target.id, type_=PG_UUID(as_uuid=True))
        await self.db.execute(
            update(RouteModel)
            .where(RouteModel.id == route_id, ~RouteModel.allowed_users_ids.contains([target.id]))
            .values(allowed_users_ids=func.array_append(RouteModel.allowed_users_ids, uid))
        )
        await self.db.commit()

    async def unassign(self, actor: UserModel, user_id: UUID, route_id: UUID) -> dict:
        """Quita al usuario (siempre se permite) y devuelve lo que tenía pendiente en esa ruta, para avisar."""
        target = await self.get_target(actor, user_id, must_be_active=False)
        await self._route_of_user_brand(target, route_id)
        pending = (await self._pending(target.id, [route_id])).get(route_id, (0, 0))
        uid = literal(target.id, type_=PG_UUID(as_uuid=True))
        removed = await self.db.execute(
            update(RouteModel)
            .where(RouteModel.id == route_id, RouteModel.allowed_users_ids.contains([target.id]))
            .values(allowed_users_ids=func.array_remove(RouteModel.allowed_users_ids, uid))
        )
        await self.db.commit()
        return {"removed": removed.rowcount > 0, "pending_payments": pending[0], "open_liquidations": pending[1]}
