from uuid import UUID
from typing import Optional, List, Union
from fastapi import HTTPException
from ..domain.repositories.expense_repository import AbstractExpenseRepository, AbstractExpenseConceptRepository
from ..domain.entities.expense import Expense, ExpenseConcept
from ..infrastructure.models.models import UserType
from ..infrastructure.models.route_model import RouteModel
from ..infrastructure.models.user_model import UserModel
from ..core.exceptions import NotFoundException
from ..core.pagination import PaginationParams, Page, page_or_list
from ..presentation.shemas.expense_shema import ExpenseCreate, ExpenseUpdate, ExpenseConceptCreate, ExpenseConceptUpdate, ExpenseFilters

class ExpenseUseCases:
    user: Optional[UserModel] = None

    def __init__(self, repository: AbstractExpenseRepository):
        self.repository = repository

    async def _ensure_route_access(self, route_id: UUID) -> RouteModel:
        route = await self.repository.get_route(route_id)

        if self.user and self.user.brand_id and route.brand_id != self.user.brand_id:
            raise NotFoundException("Ruta no encontrada")

        if self.user and self.user.type_user not in (UserType.dev, UserType.super) \
                and self.user.id not in (route.allowed_users_ids or []):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta ruta")

        return route

    async def _ensure_concept_matches_route(self, route: RouteModel, concept_id: UUID, *, reject_inactive: bool) -> None:
        concept = await self.repository.get_concept(concept_id)

        if concept.brand_id != route.brand_id:
            raise HTTPException(status_code=400, detail="El concepto no pertenece a la marca de la ruta")

        if reject_inactive and not concept.active:
            raise HTTPException(status_code=400, detail="El concepto de gasto está desactivado")

    async def get_expense(self, expense_id: UUID) -> Expense:
        expense = await self.repository.get_expense_by_id(expense_id)
        await self._ensure_route_access(expense.route_id)
        return expense

    async def list_expenses(self, filters: ExpenseFilters, params: Optional[PaginationParams] = None) -> Union[Page[Expense], List[Expense]]:
        items, total = await self.repository.list_expenses(filters, params)
        return page_or_list(items, total, params)

    async def create_expense(self, expense: ExpenseCreate) -> Optional[Expense]:
        route = await self._ensure_route_access(expense.route_id)
        await self._ensure_concept_matches_route(route, expense.expensesconcept_id, reject_inactive=True)

        data = expense.model_dump(exclude={"user_generated"})
        user_generated = (self.user.full_name or self.user.username) if self.user else ""
        new_expense = Expense(**data, user_generated=user_generated)
        return await self.repository.create_expense(new_expense)

    async def update_expense(self, expense: ExpenseUpdate) -> Optional[Expense]:
        existing = await self.repository.get_expense_by_id(expense.id)
        await self._ensure_route_access(existing.route_id)

        route = await self._ensure_route_access(expense.route_id)
        await self._ensure_concept_matches_route(
            route,
            expense.expensesconcept_id,
            reject_inactive=expense.expensesconcept_id != existing.expensesconcept_id,
        )
        return await self.repository.update_expense(expense)

    async def toggle_expense(self, expense_id: UUID) -> Expense:
        existing = await self.repository.get_expense_by_id(expense_id)
        await self._ensure_route_access(existing.route_id)
        return await self.repository.toggle_expense(expense_id)

    async def delete_expense(self, expense_id: UUID):
        existing = await self.repository.get_expense_by_id(expense_id)
        await self._ensure_route_access(existing.route_id)
        return await self.repository.delete_expense(expense_id)

class ExpenseConceptUseCases:
    user: Optional[UserModel] = None

    def __init__(self, repository: AbstractExpenseConceptRepository):
        self.repository = repository

    async def _get_accessible_concept(self, concept_id: UUID) -> ExpenseConcept:
        concept = await self.repository.get_expense_concept_by_id(concept_id)

        if self.user and self.user.brand_id and concept.brand_id != self.user.brand_id:
            raise NotFoundException("Concepto de gasto no encontrado")

        return concept

    async def get_concept(self, concept_id: UUID) -> ExpenseConcept:
        return await self._get_accessible_concept(concept_id)

    async def list_concepts(self, filters: Optional[dict] = None) -> List[ExpenseConcept]:
        return await self.repository.list_expense_concepts(filters or {})

    async def create_concept(self, concept: ExpenseConceptCreate) -> Optional[ExpenseConcept]:
        data = concept.model_dump()

        if self.user and self.user.brand_id:
            data["brand_id"] = self.user.brand_id
        elif not data.get("brand_id"):
            raise HTTPException(status_code=400, detail="Debes indicar la marca del concepto")

        new_concept = ExpenseConcept(**data)
        return await self.repository.create_expense_concept(new_concept)

    async def update_concept(self, concept: ExpenseConceptUpdate) -> Optional[ExpenseConcept]:
        await self._get_accessible_concept(concept.id)
        return await self.repository.update_expense_concept(concept)

    async def toggle_concept(self, concept_id: UUID) -> ExpenseConcept:
        await self._get_accessible_concept(concept_id)
        return await self.repository.toggle_expense_concept(concept_id)

    async def delete_concept(self, concept_id: UUID):
        await self._get_accessible_concept(concept_id)
        return await self.repository.delete_expense_concept(concept_id)
