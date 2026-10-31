from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.expense_repository import ExpenseConceptRepository
from ...use_cases.expense_cases import ExpenseConceptUseCases
from ..shemas.expense_shema import ExpenseConceptRead, ExpenseConceptUpdate, ExpenseConceptCreate, ExpenseFilters
from ...use_cases.expense_cases import ExpenseConceptUseCases
from ...infrastructure.utils.require_authentication import require_authentication

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_concept_repository(db: AsyncSession = Depends(get_db)) -> ExpenseConceptRepository:
    return ExpenseConceptRepository(db)

def get_concept_usecases(repository: ExpenseConceptRepository = Depends(get_concept_repository)) -> ExpenseConceptUseCases:
    return ExpenseConceptUseCases(repository)

@router.get("/{concept_id}", response_model=Optional[ExpenseConceptRead])
async def read_concept(concept_id: UUID, usecases: ExpenseConceptUseCases = Depends(get_concept_usecases)):
    return await usecases.get_concept(concept_id)

@router.get("/", response_model=List[ExpenseConceptRead])
async def list_concepts(usecases: ExpenseConceptUseCases = Depends(get_concept_usecases)):
    return await usecases.list_concepts()

@router.post("/", response_model=ExpenseConceptRead, status_code=status.HTTP_201_CREATED)
async def create_concept(concept_in: ExpenseConceptCreate, usecases: ExpenseConceptUseCases = Depends(get_concept_usecases)):
    return await usecases.create_concept(concept=concept_in)

@router.put("/{concept_id}", response_model=ExpenseConceptRead)
async def update_concept(concept_in: ExpenseConceptUpdate, usecases: ExpenseConceptUseCases = Depends(get_concept_usecases)):
    return await usecases.update_concept(concept=concept_in)

@router.delete("/{concept_id}")
async def delete_concept(concept_id: UUID, usecases: ExpenseConceptUseCases = Depends(get_concept_usecases)):
    return await usecases.delete_concept(concept_id)