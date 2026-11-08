from uuid import UUID
from ...domain.entities.expense import Expense, ExpenseConcept
from ...domain.repositories.expense_repository import AbstractExpenseRepository, AbstractExpenseConceptRepository
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.expense_model import ExpenseModel, ExpenseConceptModel
from ..models.route_model import RouteModel
from ..models.models import UserType
from ...presentation.shemas.expense_shema import ExpenseUpdate, ExpenseConceptUpdate, ExpenseFilters
from app.infrastructure.utils.validator_errors import ValidatorErrors
from app.core.exceptions import ConflictException, NotFoundException
from app.core.pagination import PaginationParams, paginate_or_all
from datetime import datetime


def _is_active_filter(filters_dict: dict) -> bool:
    return filters_dict.get("active", True) in ["True", True, "true"]


class ExpenseRepository(AbstractExpenseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_route(self, route_id: UUID) -> RouteModel:
        result = await self.db.execute(select(RouteModel).where(RouteModel.id == route_id))
        route = result.scalars().first()
        if not route:
            raise NotFoundException("Ruta no encontrada")
        return route

    async def get_concept(self, concept_id: UUID) -> ExpenseConceptModel:
        result = await self.db.execute(
            select(ExpenseConceptModel).where(ExpenseConceptModel.id == concept_id)
        )
        concept = result.scalars().first()
        if not concept:
            raise NotFoundException("Concepto de gasto no encontrado")
        return concept

    async def get_queryset(self, filters: ExpenseFilters):
        filters_dict = dict(filters)
        text_search = filters_dict.get("text", None)
        route_id = filters_dict.get("route_id", None)
        date = filters_dict.get("date", None)
        expense_concept_id = filters_dict.get("expense_concept_id", None)
        date_liquidated = filters_dict.get("date_liquidated", None)

        stmt = (
            select(ExpenseModel)
            .join(RouteModel, ExpenseModel.route_id == RouteModel.id)
            .options(selectinload(ExpenseModel.expensesconcept))
            .where(ExpenseModel.active == _is_active_filter(filters_dict))
        )

        if self.user.brand_id:
            stmt = stmt.where(RouteModel.brand_id == self.user.brand_id)

        if self.user.type_user not in (UserType.super, UserType.dev):
            stmt = stmt.where(RouteModel.allowed_users_ids.contains([self.user.id]))

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

    async def _load_model(self, expense_id: UUID) -> Optional[ExpenseModel]:
        result = await self.db.execute(
            select(ExpenseModel)
            .where(ExpenseModel.id == expense_id)
            .options(selectinload(ExpenseModel.expensesconcept))
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def get_expense_by_id(self, expense_id: UUID) -> Expense:
        try:
            model = await self._load_model(expense_id)
            if not model:
                raise NotFoundException("Gasto no encontrado")
            return self.model_to_entity(model)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_expenses(self, filters: ExpenseFilters, params: Optional[PaginationParams] = None) -> tuple[List[Expense], int]:
        try:
            stmt = (await self.get_queryset(filters)).order_by(
                ExpenseModel.date.desc(), ExpenseModel.created_at.desc(), ExpenseModel.id
            )
            return await paginate_or_all(self.db, stmt, params, self.model_to_entity)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_expense(self, expense: Expense) -> Optional[Expense]:
        orm_expense = self.entity_to_model(expense)
        self.db.add(orm_expense)
        try:
            await self.db.commit()
            return self.model_to_entity(await self._load_model(orm_expense.id))
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_expense(self, expense: ExpenseUpdate) -> Optional[Expense]:
        try:
            current_expense = await self._load_model(expense.id)

            if not current_expense:
                raise NotFoundException("Gasto no encontrado")

            update_data = expense.model_dump(exclude_unset=True)

            current_expense = self.update_values(update_data, current_model=current_expense)

            await self.db.commit()
            return self.model_to_entity(await self._load_model(expense.id))

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def toggle_expense(self, expense_id: UUID) -> Expense:
        try:
            current_expense = await self._load_model(expense_id)

            if not current_expense:
                raise NotFoundException("Gasto no encontrado")

            current_expense.active = not current_expense.active

            await self.db.commit()
            return self.model_to_entity(await self._load_model(expense_id))

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

    async def _get_model(self, concept_id: UUID) -> ExpenseConceptModel:
        result = await self.db.execute(
            select(ExpenseConceptModel).where(ExpenseConceptModel.id == concept_id)
        )
        model = result.scalars().first()
        if not model:
            raise NotFoundException("Concepto de gasto no encontrado")
        return model

    async def get_expense_concept_by_id(self, concept_id: UUID) -> ExpenseConcept:
        try:
            return self.model_to_entity(await self._get_model(concept_id))
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_expense_concepts(self, filters: dict) -> List[ExpenseConcept]:
        try:
            stmt = select(ExpenseConceptModel).where(
                ExpenseConceptModel.active == _is_active_filter(filters)
            )

            if self.user.brand_id:
                stmt = stmt.where(ExpenseConceptModel.brand_id == self.user.brand_id)

            stmt = stmt.order_by(ExpenseConceptModel.concept, ExpenseConceptModel.id)
            result = await self.db.execute(stmt)
            return [self.model_to_entity(m) for m in result.scalars().all()]
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
            current_concept = await self._get_model(concept.id)

            update_data = concept.model_dump(exclude_unset=True)

            current_concept = self.update_values(update_data, current_model=current_concept)

            await self.db.commit()
            await self.db.refresh(current_concept)
            return self.model_to_entity(current_concept)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def toggle_expense_concept(self, concept_id: UUID) -> ExpenseConcept:
        try:
            current_concept = await self._get_model(concept_id)
            current_concept.active = not current_concept.active

            await self.db.commit()
            await self.db.refresh(current_concept)
            return self.model_to_entity(current_concept)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def delete_expense_concept(self, concept_id:UUID):
        try:
            current_concept = await self._get_model(concept_id)

            current_concept.active = False

            await self.db.commit()
            await self.db.refresh(current_concept)
            return "Concepto de gasto eliminado exitosamente"

        except IntegrityError as e:
            await self.db.rollback()
            expense_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(expense_message)
