from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from ...core.pagination import filters_from_request
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.expense_repository import ExpenseConceptRepository
from ...use_cases.expense_cases import ExpenseConceptUseCases
from ..shemas.expense_shema import ExpenseConceptRead, ExpenseConceptUpdate, ExpenseConceptCreate
from app.infrastructure.models.user_model import UserModel
from ...infrastructure.utils.require_authentication import require_authentication
from ...infrastructure.utils.require_role import require_role

_ALL_ROLES = ("01", "02", "03", "04", "05")
_MANAGE_ROLES = ("01", "02", "03")

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_concept_repository(db: AsyncSession = Depends(get_db)) -> ExpenseConceptRepository:
    return ExpenseConceptRepository(db)

def _usecases_for(*roles: str):
    def dependency(
        user: UserModel = Depends(require_role(*roles)),
        repository: ExpenseConceptRepository = Depends(get_concept_repository),
    ) -> ExpenseConceptUseCases:
        usecases = ExpenseConceptUseCases(repository)
        usecases.user = user
        repository.user = user
        return usecases
    return dependency

get_concept_usecases = _usecases_for(*_ALL_ROLES)
get_concept_manage_usecases = _usecases_for(*_MANAGE_ROLES)

@router.get("/{concept_id}", response_model=ExpenseConceptRead)
async def read_concept(concept_id: UUID, usecases: ExpenseConceptUseCases = Depends(get_concept_usecases)):
    return await usecases.get_concept(concept_id)

@router.get("/", response_model=List[ExpenseConceptRead])
async def list_concepts(request: Request, usecases: ExpenseConceptUseCases = Depends(get_concept_usecases)):
    return await usecases.list_concepts(filters_from_request(request))

@router.post("/", response_model=ExpenseConceptRead, status_code=status.HTTP_201_CREATED)
async def create_concept(concept_in: ExpenseConceptCreate, usecases: ExpenseConceptUseCases = Depends(get_concept_manage_usecases)):
    return await usecases.create_concept(concept=concept_in)

@router.put("/{concept_id}", response_model=ExpenseConceptRead)
async def update_concept(concept_in: ExpenseConceptUpdate, usecases: ExpenseConceptUseCases = Depends(get_concept_manage_usecases)):
    return await usecases.update_concept(concept=concept_in)

@router.put("/{concept_id}/toggle", response_model=ExpenseConceptRead)
async def toggle_concept(concept_id: UUID, usecases: ExpenseConceptUseCases = Depends(get_concept_manage_usecases)):
    return await usecases.toggle_concept(concept_id)

@router.delete("/{concept_id}")
async def delete_concept(concept_id: UUID, usecases: ExpenseConceptUseCases = Depends(get_concept_manage_usecases)):
    return await usecases.delete_concept(concept_id)
