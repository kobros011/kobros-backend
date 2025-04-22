from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.payment_repository import PaymentRepository
from ...use_cases.payment_cases import PaymentUseCases
from ..shemas.payment_shema import PaymentRead, PaymentUpdate, PaymentCreate
from ...use_cases.payment_cases import PaymentUseCases
from ...infrastructure.utils.require_authentication import require_authentication

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_payment_repository(db: AsyncSession = Depends(get_db)) -> PaymentRepository:
    return PaymentRepository(db)

def get_payment_usecases(repository: PaymentRepository = Depends(get_payment_repository)) -> PaymentUseCases:
    return PaymentUseCases(repository)

@router.get("/{payment_id}", response_model=Optional[PaymentRead])
async def read_payment(payment_id: UUID, usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.get_payment(payment_id)

@router.get("/", response_model=List[PaymentRead])
async def list_payments(usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.list_payments()

@router.post("/", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def create_payment(payment_in: PaymentCreate, usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.create_payment(payment=payment_in)

@router.put("/{payment_id}", response_model=PaymentRead)
async def update_payment(payment_in: PaymentUpdate, usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.update_payment(payment=payment_in)

@router.delete("/{payment_id}")
async def delete_payment(payment_id: UUID, usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.delete_payment(payment_id)