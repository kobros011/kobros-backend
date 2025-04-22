from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.loan_repository import LoanRepository
from ...use_cases.loan_cases import LoanUseCases
from ..shemas.loan_shema import LoanRead, LoanUpdate, LoanCreate
from ...use_cases.loan_cases import LoanUseCases
from ...infrastructure.utils.require_authentication import require_authentication

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_loan_repository(db: AsyncSession = Depends(get_db)) -> LoanRepository:
    return LoanRepository(db)

def get_loan_usecases(repository: LoanRepository = Depends(get_loan_repository)) -> LoanUseCases:
    return LoanUseCases(repository)

@router.get("/{loan_id}", response_model=Optional[LoanRead])
async def read_loan(loan_id: UUID, usecases: LoanUseCases = Depends(get_loan_usecases)):
    return await usecases.get_loan(loan_id)

@router.get("/", response_model=List[LoanRead])
async def list_loans(usecases: LoanUseCases = Depends(get_loan_usecases)):
    return await usecases.list_loans()

@router.post("/", response_model=LoanRead, status_code=status.HTTP_201_CREATED)
async def create_loan(loan_in: LoanCreate, usecases: LoanUseCases = Depends(get_loan_usecases)):
    return await usecases.create_loan(loan=loan_in)

@router.put("/{loan_id}", response_model=LoanRead)
async def update_loan(loan_in: LoanUpdate, usecases: LoanUseCases = Depends(get_loan_usecases)):
    return await usecases.update_loan(loan=loan_in)

@router.delete("/{loan_id}")
async def read_loan(loan_id: UUID, usecases: LoanUseCases = Depends(get_loan_usecases)):
    return await usecases.delete_loan(loan_id)