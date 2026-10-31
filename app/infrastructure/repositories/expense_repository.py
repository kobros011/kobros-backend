from uuid import UUID
from ...domain.entities.expense import Expense, ExpenseConcept
from ...domain.repositories.expense_repository import AbstractExpenseRepository, AbstractExpenseConceptRepository
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.expense_model import ExpenseModel, ExpenseConceptModel
from ...presentation.shemas.expense_shema import ExpenseUpdate, ExpenseConceptUpdate, ExpenseFilters
from app.infrastructure.utils.validator_errors import ValidatorErrors
from app.core.exceptions import ConflictException, NotFoundException
from datetime import datetime

class ExpenseRepository(AbstractExpenseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stmt(self, filters: ExpenseFilters) -> select:
        filters_dict = dict(filters)
        text_search = filters_dict.get("text", None)
        route_id = filters_dict.get("route_id", None)
        date = filters_dict.get("date", None)
        expense_concept_id = filters_dict.get("expense_concept_id", None)
        date_liquidated = filters_dict.get("date_liquidated", None)

        stmt = select(ExpenseModel).options(selectinload(ExpenseModel.expensesconcept))

        if text_search and text_search.strip() and text_search.lower() != "":
            ts = text_search.strip().lower()
            stmt = stmt.where(ExpenseModel.name.ilike(f"%{ts}%"))

        if route_id:
            stmt = stmt.where(ExpenseModel.route_id == route_id)

        if date:
            date_dt = datetime.strptime(date, "%Y-%m-%d").date()
            stmt = stmt.where(ExpenseModel.date == date_dt)

        if date_liquidated:
            date_ld_dt = datetime.strptime(date_liquidated, "%Y-%m-%d").date()
            stmt = stmt.where(ExpenseModel.date_liquidated == date_ld_dt)

        if expense_concept_id:
            stmt = stmt.where(ExpenseModel.expensesconcept_id == expense_concept_id)

        return stmt
 
    async def get_expense_by_id(self, expense_id: UUID) -> Optional[Expense]:
        try:

            stmt = select(ExpenseModel).where(ExpenseModel.id == expense_id).options(selectinload(ExpenseModel.expensesconcept))

            result = await self.db.execute(stmt)
            model = result.scalars().first()
            return self.model_to_entity(model) if model else None
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_expenses(self, filters: ExpenseFilters) -> List[Expense]:
        try:

            stmt = await self.get_stmt(filters)

            result = await self.db.execute(stmt)
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


class ExpenseConceptRepository(AbstractExpenseConceptRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_expense_concept_by_id(self, concept_id: UUID) -> Optional[ExpenseConcept]:
        try:
            result = await self.db.execute(
                select(ExpenseConceptModel).where(ExpenseConceptModel.id == concept_id)
            )
            model = result.scalars().first()
            return self.model_to_entity(model) if model else None
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_expense_concepts(self) -> List[ExpenseConcept]:
        try:
            result = await self.db.execute(select(ExpenseConceptModel).order_by('concept'))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_expense_concept(self, concept: ExpenseConcept) -> Optional[ExpenseConcept]:
        orm_concept = self.entity_to_model(concept)
        self.db.add(orm_concept)
        try:
            await self.db.commit()
            await self.db.refresh(orm_concept)
            return self.model_to_entity(orm_concept)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_expense_concept(self, concept: ExpenseConceptUpdate) -> Optional[ExpenseConcept]:
        try:
            result = await self.db.execute(
                select(ExpenseConceptModel).where(ExpenseConceptModel.id == concept.id)
            )
            current_concept = result.scalars().first()

            if not current_concept:
                raise NotFoundException("Concepto de gasto no encontrado")

            update_data = concept.model_dump(exclude_unset=True)

            current_concept = self.update_values(update_data, current_model=current_concept)

            await self.db.commit()
            await self.db.refresh(current_concept)
            return self.model_to_entity(current_concept)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def delete_expense_concept(self, concept_id:UUID):
        try:
            result = await self.db.execute(
                select(ExpenseConceptModel).where(ExpenseConceptModel.id == concept_id)
            )
            current_concept = result.scalars().first()

            if not current_concept:
                raise NotFoundException("El Concepto de Gasto no fue encontrado")
            
            current_concept.active = False

            await self.db.commit()
            await self.db.refresh(current_concept)
            return "Concepto de gasto eliminado exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            expense_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(expense_message)
