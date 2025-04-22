from uuid import UUID
from ...domain.entities.expense import Expense
from ...domain.repositories.expense_repository import AbstractExpenseRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.expense_model import ExpenseModel
from ...presentation.shemas.expense_shema import ExpenseUpdate
from app.infrastructure.utils.validator_errors import ValidatorErrors
from app.core.exceptions import ConflictException, NotFoundException


class ExpenseRepository(AbstractExpenseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
 
    async def get_expense_by_id(self, expense_id: UUID) -> Optional[Expense]:
        try:
            result = await self.db.execute(
                select(ExpenseModel).where(ExpenseModel.id == expense_id)
            )
            model = result.scalars().first()
            return self.model_to_entity(model) if model else None
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_expenses(self) -> List[Expense]:
        try:
            result = await self.db.execute(select(ExpenseModel))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_expense(self, expense: Expense) -> Optional[Expense]:
        orm_expense = self.entity_to_model(expense)
        self.db.add(orm_expense)
        try:
            await self.db.commit()
            await self.db.refresh(orm_expense)
            return self.model_to_entity(orm_expense)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_expense(self, expense: ExpenseUpdate) -> Optional[Expense]:
        try:
            result = await self.db.execute(
                select(ExpenseModel).where(ExpenseModel.id == expense.id)
            )
            current_expense = result.scalars().first()

            if not current_expense:
                raise NotFoundException("Gasto no encontrado")

            update_data = expense.model_dump(exclude_unset=True)

            current_expense = self.update_values(update_data, current_model=current_expense)

            await self.db.commit()
            await self.db.refresh(current_expense)
            return self.model_to_entity(current_expense)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def delete_expense(self, expense_id:UUID):
        try:
            result = await self.db.execute(
                select(ExpenseModel).where(ExpenseModel.id == expense_id)
            )
            current_expense = result.scalars().first()

            if not current_expense:
                raise NotFoundException("El Gasto no fue encontrado")
            
            current_expense.active = False

            await self.db.commit()
            await self.db.refresh(current_expense)
            return "Gasto eliminado exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            expense_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(expense_message)
