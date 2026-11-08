from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List, Union
from ...core.pagination import Page, PaginationParams, filters_from_request, optional_pagination_params
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.expense_repository import ExpenseRepository
from ...use_cases.expense_cases import ExpenseUseCases
from ..shemas.expense_shema import ExpenseRead, ExpenseUpdate, ExpenseCreate
from app.infrastructure.models.user_model import UserModel
from ...infrastructure.utils.require_authentication import require_authentication
from ...infrastructure.utils.require_role import require_role

_ALL_ROLES = ("01", "02", "03", "04", "05")
_MANAGE_ROLES = ("01", "02", "03")

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_expense_repository(db: AsyncSession = Depends(get_db)) -> ExpenseRepository:
    return ExpenseRepository(db)

def _usecases_for(*roles: str):
    def dependency(
        user: UserModel = Depends(require_role(*roles)),
        repository: ExpenseRepository = Depends(get_expense_repository),
    ) -> ExpenseUseCases:
        usecases = ExpenseUseCases(repository)
        usecases.user = user
        repository.user = user
        return usecases
    return dependency

get_expense_usecases = _usecases_for(*_ALL_ROLES)
get_expense_manage_usecases = _usecases_for(*_MANAGE_ROLES)

@router.get("/{expense_id}", response_model=ExpenseRead)
async def read_expense(expense_id: UUID, usecases: ExpenseUseCases = Depends(get_expense_usecases)):
    return await usecases.get_expense(expense_id)

@router.get("/", response_model=Union[Page[ExpenseRead], List[ExpenseRead]])
async def list_expenses(
    request: Request,
    pagination: Optional[PaginationParams] = Depends(optional_pagination_params),
    usecases: ExpenseUseCases = Depends(get_expense_usecases),
):
    return await usecases.list_expenses(filters_from_request(request), pagination)

@router.post("/", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(expense_in: ExpenseCreate, usecases: ExpenseUseCases = Depends(get_expense_usecases)):
    return await usecases.create_expense(expense=expense_in)

@router.put("/{expense_id}", response_model=ExpenseRead)
async def update_expense(expense_in: ExpenseUpdate, usecases: ExpenseUseCases = Depends(get_expense_manage_usecases)):
    return await usecases.update_expense(expense=expense_in)

@router.put("/{expense_id}/toggle", response_model=ExpenseRead)
async def toggle_expense(expense_id: UUID, usecases: ExpenseUseCases = Depends(get_expense_manage_usecases)):
    return await usecases.toggle_expense(expense_id)

@router.delete("/{expense_id}")
async def delete_expense(expense_id: UUID, usecases: ExpenseUseCases = Depends(get_expense_manage_usecases)):
    return await usecases.delete_expense(expense_id)
