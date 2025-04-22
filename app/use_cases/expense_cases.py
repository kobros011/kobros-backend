from uuid import UUID
from typing import Optional, List
from ..domain.repositories.expense_repository import AbstractExpenseRepository
from ..domain.entities.expense import Expense
from ..presentation.shemas.expense_shema import ExpenseCreate, ExpenseUpdate

class ExpenseUseCases:
    def __init__(self, repository: AbstractExpenseRepository):
        self.repository = repository

    async def get_expense(self, expense_id: UUID) -> Optional[Expense]:
        return await self.repository.get_expense_by_id(expense_id)
    
    async def list_expenses(self) -> List[Expense]:
        return await self.repository.list_expenses()
    
    async def create_expense(self, expense: ExpenseCreate) -> Optional[Expense]:
        new_expense = Expense(**expense.model_dump())
        return await self.repository.create_expense(new_expense)
    
    async def update_expense(self, expense: ExpenseUpdate) -> Optional[Expense]:
        return await self.repository.update_expense(expense)
    
    async def delete_expense(self, expense_id: UUID):
        return await self.repository.delete_expense(expense_id)