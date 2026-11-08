from uuid import UUID
from datetime import datetime, date as date_type
from ...domain.entities.liquidation import Liquidation
from ...domain.repositories.liquidation_repository import AbstractLiquidationRepository
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.liquidation_model import LiquidationModel
from ..models.payment_model import PaymentModel
from ..models.loan_model import LoanModel
from ..models.client_route_model import ClientRouteModel
from ..models.expense_model import ExpenseModel
from ...presentation.shemas.liquidation_shema import LiquidationUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException


class LiquidationRepository(AbstractLiquidationRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_liquidation_by_id(self, liquidation_id: UUID) -> Optional[Liquidation]:
        try:
            result = await self.db.execute(
                select(LiquidationModel).where(LiquidationModel.id == liquidation_id)
            )
            model = result.scalars().first()
            if not model:
                raise NotFoundException("Liquidación no encontrada")
            return self.model_to_entity(model)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_liquidations(self) -> List[Liquidation]:
        try:
            result = await self.db.execute(select(LiquidationModel))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_liquidation(self, liquidation: Liquidation, route_id: UUID, liq_date: date_type) -> Optional[Liquidation]:
        # Check for duplicate: same route + date
        existing = await self.db.execute(
            select(LiquidationModel).where(
                LiquidationModel.route_id == route_id,
                LiquidationModel.date == liq_date,
                LiquidationModel.active == True,
            )
        )
        if existing.scalars().first():
            raise ConflictException("Ya existe una liquidación para esta ruta y fecha")

        # Calculate total_value_charged from payments not yet liquidated
        payments_result = await self.db.execute(
            select(PaymentModel)
            .join(LoanModel, PaymentModel.loan_id == LoanModel.id)
            .join(ClientRouteModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(
                ClientRouteModel.route_id == route_id,
                PaymentModel.pay_date == liq_date,
                PaymentModel.liquidated == False,
            )
        )
        payments = payments_result.scalars().all()
        total_charged = sum(p.applied or 0 for p in payments)

        # Calculate total_value_expenses from expenses not yet liquidated
        expenses_result = await self.db.execute(
            select(ExpenseModel).where(
                ExpenseModel.route_id == route_id,
                ExpenseModel.date == liq_date,
                ExpenseModel.liquidated == False,
                ExpenseModel.active == True,
            )
        )
        expenses = expenses_result.scalars().all()
        total_expenses = sum(e.value or 0 for e in expenses)

        liquidation.total_value_charged = total_charged
        liquidation.total_value_expenses = total_expenses

        orm_liquidation = self.entity_to_model(liquidation)
        self.db.add(orm_liquidation)

        try:
            await self.db.flush()

            # Mark payments and expenses as liquidated
            today = date_type.today()
            for p in payments:
                p.liquidated = True
                p.date_liquidated = today
            for e in expenses:
                e.liquidated = True
                e.date_liquidated = today

            await self.db.commit()
            await self.db.refresh(orm_liquidation)
            return self.model_to_entity(orm_liquidation)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_liquidation(self, liquidation: LiquidationUpdate) -> Optional[Liquidation]:
        try:
            result = await self.db.execute(
                select(LiquidationModel).where(LiquidationModel.id == liquidation.id)
            )
            current_liquidation = result.scalars().first()

            if not current_liquidation:
                raise NotFoundException("Liquidación no encontrada")

            update_data = liquidation.model_dump(exclude_unset=True)
            current_liquidation = self.update_values(update_data, current_model=current_liquidation)

            await self.db.commit()
            await self.db.refresh(current_liquidation)
            return self.model_to_entity(current_liquidation)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def confirm_liquidation(self, liquidation_id: UUID, confirmed_by: UUID) -> Optional[Liquidation]:
        try:
            result = await self.db.execute(
                select(LiquidationModel).where(LiquidationModel.id == liquidation_id)
            )
            current_liquidation = result.scalars().first()

            if not current_liquidation:
                raise NotFoundException("Liquidación no encontrada")

            if current_liquidation.admin_confirmed_at:
                raise ConflictException("La liquidación ya fue confirmada")

            current_liquidation.admin_confirmed_at = datetime.utcnow()
            current_liquidation.admin_confirmed_by = confirmed_by

            await self.db.commit()
            await self.db.refresh(current_liquidation)
            return self.model_to_entity(current_liquidation)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def delete_liquidation(self, liquidation_id: UUID):
        try:
            result = await self.db.execute(
                select(LiquidationModel).where(LiquidationModel.id == liquidation_id)
            )
            current_liquidation = result.scalars().first()

            if not current_liquidation:
                raise NotFoundException("La liquidación no fue encontrada")

            current_liquidation.active = False

            await self.db.commit()
            await self.db.refresh(current_liquidation)
            return "Liquidación eliminada exitosamente"

        except IntegrityError as e:
            await self.db.rollback()
            liquidation_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(liquidation_message)
