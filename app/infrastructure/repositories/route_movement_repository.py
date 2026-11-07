from uuid import UUID
from typing import Sequence
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...domain.entities.route_movement import RouteMovement
from ...domain.repositories.route_movement_repository import AbstractRouteMovementRepository
from ..models.route_movement_model import RouteMovementModel
from ..models.route_model import RouteModel
from ..models.payment_model import PaymentModel
from ..models.loan_model import LoanModel
from ..models.client_route_model import ClientRouteModel
from ..models.expense_model import ExpenseModel
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException
from ...core.pagination import PaginationParams, paginate


class RouteMovementRepository(AbstractRouteMovementRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_route(self, route_id: UUID) -> RouteModel:
        result = await self.db.execute(select(RouteModel).where(RouteModel.id == route_id))
        route = result.scalars().first()
        if not route:
            raise NotFoundException("Ruta no encontrada")
        return route

    async def _lock_route(self, route_id: UUID) -> RouteModel:
        result = await self.db.execute(
            select(RouteModel).where(RouteModel.id == route_id).with_for_update()
        )
        route = result.scalars().first()
        if not route:
            raise NotFoundException("Ruta no encontrada")
        return route

    async def _compute_summary(self, route: RouteModel) -> dict:
        route_id = route.id

        movements_result = await self.db.execute(
            select(RouteMovementModel.type, func.coalesce(func.sum(RouteMovementModel.value), 0))
            .where(RouteMovementModel.route_id == route_id, RouteMovementModel.active == True)
            .group_by(RouteMovementModel.type)
        )
        movement_totals = {row[0]: float(row[1]) for row in movements_result.all()}
        ingresos = movement_totals.get('INGRESO', 0.0)
        retiros = movement_totals.get('RETIRO', 0.0)

        cobros_result = await self.db.execute(
            select(func.coalesce(func.sum(PaymentModel.applied), 0))
            .join(LoanModel, PaymentModel.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(ClientRouteModel.route_id == route_id, PaymentModel.active == True)
        )
        cobros = float(cobros_result.scalar() or 0)

        gastos_result = await self.db.execute(
            select(func.coalesce(func.sum(ExpenseModel.value), 0))
            .where(ExpenseModel.route_id == route_id, ExpenseModel.active == True)
        )
        gastos = float(gastos_result.scalar() or 0)

        desembolsos_result = await self.db.execute(
            select(func.coalesce(func.sum(LoanModel.value_capital), 0))
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(ClientRouteModel.route_id == route_id, LoanModel.active == True)
        )
        desembolsos = float(desembolsos_result.scalar() or 0)

        initial_value = float(route.initial_value or 0)
        saldo = initial_value + ingresos - retiros + cobros - gastos - desembolsos

        return {
            "initial_value": initial_value,
            "ingresos": ingresos,
            "retiros": retiros,
            "cobros": cobros,
            "gastos": gastos,
            "desembolsos": desembolsos,
            "saldo": saldo,
        }

    async def get_summary_for_route(self, route: RouteModel) -> dict:
        return await self._compute_summary(route)

    async def list_movements(self, route_id: UUID, params: PaginationParams) -> tuple[Sequence[RouteMovement], int]:
        stmt = (
            select(RouteMovementModel)
            .options(selectinload(RouteMovementModel.user))
            .where(RouteMovementModel.route_id == route_id, RouteMovementModel.active == True)
            .order_by(RouteMovementModel.created_at.desc(), RouteMovementModel.id.desc())
        )
        models, total = await paginate(self.db, stmt, params)
        return [self.model_to_entity(m) for m in models], total

    async def create_movement(self, route_id: UUID, movement_type: str, value: float, concept: str) -> RouteMovement:
        try:
            route = await self._lock_route(route_id)
            summary = await self._compute_summary(route)

            if movement_type == 'RETIRO' and value > summary['saldo']:
                raise ConflictException(
                    f"El retiro supera el saldo disponible de la ruta ({summary['saldo']:.2f})."
                )

            orm_movement = RouteMovementModel(
                route_id=route_id,
                type=movement_type,
                value=value,
                concept=concept,
                user_id=self.user.id if self.user else None,
            )
            self.db.add(orm_movement)
            await self.db.commit()

            result = await self.db.execute(
                select(RouteMovementModel)
                .options(selectinload(RouteMovementModel.user))
                .where(RouteMovementModel.id == orm_movement.id)
            )
            refreshed = result.scalars().first()
            return self.model_to_entity(refreshed)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
