from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List, Union
from ...core.pagination import Page, PaginationParams, filters_from_request, optional_pagination_params
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.loan_repository import LoanRepository
from ...use_cases.loan_cases import LoanUseCases
from ..shemas.loan_shema import LoanRead, LoanUpdate, LoanCreate, LoanReadFull
from ...use_cases.loan_cases import LoanUseCases
from ...infrastructure.utils.require_authentication import require_authentication, get_current_user
from ...infrastructure.utils.require_role import require_role
from ...infrastructure.models.user_model import UserModel

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_loan_repository(db: AsyncSession = Depends(get_db)) -> LoanRepository:
    return LoanRepository(db)

def get_loan_usecases(repository: LoanRepository = Depends(get_loan_repository)) -> LoanUseCases:
    return LoanUseCases(repository)

@router.get("/{loan_id}", response_model=Optional[LoanReadFull])
async def read_loan(loan_id: UUID, usecases: LoanUseCases = Depends(get_loan_usecases)):
    return await usecases.get_loan(loan_id)

@router.get("/", response_model=Union[Page[LoanReadFull], List[LoanReadFull]])
async def list_loans(
    request: Request,
    pagination: Optional[PaginationParams] = Depends(optional_pagination_params),
    usecases: LoanUseCases = Depends(get_loan_usecases),
    user: UserModel = Depends(get_current_user),
):
    return await usecases.list_loans(filters_from_request(request), pagination, user)

@router.post("/", response_model=LoanRead, status_code=status.HTTP_201_CREATED)
async def create_loan(
    loan_in: LoanCreate,
    usecases: LoanUseCases = Depends(get_loan_usecases),
    user: UserModel = Depends(require_role("01", "02", "03", "04", "05")),
):
    return await usecases.create_loan(loan=loan_in, user=user)

@router.put("/{loan_id}", response_model=LoanRead)
async def update_loan(loan_in: LoanUpdate, usecases: LoanUseCases = Depends(get_loan_usecases)):
    return await usecases.update_loan(loan=loan_in)

@router.delete("/{loan_id}")
async def read_loan(loan_id: UUID, usecases: LoanUseCases = Depends(get_loan_usecases)):
    return await usecases.delete_loan(loan_id)