from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.expense_repository import ExpenseRepository
from ...use_cases.expense_cases import ExpenseUseCases
from ..shemas.expense_shema import ExpenseRead, ExpenseUpdate, ExpenseCreate
from ...use_cases.expense_cases import ExpenseUseCases
from ...infrastructure.utils.require_authentication import require_authentication

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_expense_repository(db: AsyncSession = Depends(get_db)) -> ExpenseRepository:
    return ExpenseRepository(db)

def get_expense_usecases(repository: ExpenseRepository = Depends(get_expense_repository)) -> ExpenseUseCases:
    return ExpenseUseCases(repository)

@router.get("/{expense_id}", response_model=Optional[ExpenseRead])
async def read_expense(expense_id: UUID, usecases: ExpenseUseCases = Depends(get_expense_usecases)):
    return await usecases.get_expense(expense_id)

@router.get("/", response_model=List[ExpenseRead])
async def list_expenses(usecases: ExpenseUseCases = Depends(get_expense_usecases)):
    return await usecases.list_expenses()

@router.post("/", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(expense_in: ExpenseCreate, usecases: ExpenseUseCases = Depends(get_expense_usecases)):
    return await usecases.create_expense(expense=expense_in)

@router.put("/{expense_id}", response_model=ExpenseRead)
async def update_expense(expense_in: ExpenseUpdate, usecases: ExpenseUseCases = Depends(get_expense_usecases)):
    return await usecases.update_expense(expense=expense_in)

@router.delete("/{expense_id}")
async def delete_expense(expense_id: UUID, usecases: ExpenseUseCases = Depends(get_expense_usecases)):
    return await usecases.delete_expense(expense_id)