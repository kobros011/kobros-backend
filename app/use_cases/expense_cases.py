from uuid import UUID
from typing import Optional, List
from ..domain.repositories.expense_repository import AbstractExpenseRepository, AbstractExpenseConceptRepository
from ..domain.entities.expense import Expense, ExpenseConcept
from ..presentation.shemas.expense_shema import ExpenseCreate, ExpenseUpdate, ExpenseConceptCreate, ExpenseConceptUpdate, ExpenseConceptRead, ExpenseFilters

class ExpenseUseCases:
    def __init__(self, repository: AbstractExpenseRepository):
        self.repository = repository

    async def get_expense(self, expense_id: UUID) -> Optional[Expense]:
        return await self.repository.get_expense_by_id(expense_id)
    
    async def list_expenses(self, filters: ExpenseFilters) -> List[Expense]:
        return await self.repository.list_expenses(filters)
    
    async def create_expense(self, expense: ExpenseCreate) -> Optional[Expense]:
        new_expense = Expense(**expense.model_dump())
        return await self.repository.create_expense(new_expense)
    
    async def update_expense(self, expense: ExpenseUpdate) -> Optional[Expense]:
        return await self.repository.update_expense(expense)
    
    async def delete_expense(self, expense_id: UUID):
        return await self.repository.delete_expense(expense_id)

class ExpenseConceptUseCases:
    def __init__(self, repository: AbstractExpenseConceptRepository):
        self.repository = repository

    async def get_concept(self, concept_id: UUID) -> Optional[ExpenseConceptRead]:
        return await self.repository.get_expense_concept_by_id(concept_id)

    async def list_concepts(self) -> List[ExpenseConceptRead]:
        return await self.repository.list_expense_concepts()

    async def create_concept(self, concept: ExpenseConceptCreate) -> Optional[ExpenseConceptRead]:
        new_concept = ExpenseConcept(**concept.model_dump())
        return await self.repository.create_expense_concept(new_concept)

    async def update_concept(self, concept: ExpenseConceptUpdate) -> Optional[ExpenseConceptRead]:
        return await self.repository.update_expense_concept(concept)

    async def delete_concept(self, concept_id: UUID):
        return await self.repository.delete_expense(concept_id)