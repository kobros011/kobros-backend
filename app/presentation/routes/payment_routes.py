from fastapi import APIRouter, Depends, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.payment_repository import PaymentRepository
from ...use_cases.payment_cases import PaymentUseCases
from ..shemas.payment_shema import PaymentRead, PaymentUpdate, PaymentCreate
from ...use_cases.payment_cases import PaymentUseCases
from ...infrastructure.utils.require_authentication import require_authentication, get_current_user
from ...infrastructure.models.user_model import UserModel
from ...infrastructure.repositories.payment_history_repository import PaymentHistoryRepository
from ...use_cases.payment_history_cases import PaymentHistoryUseCases
from ...core.pagination import PaginationParams, pagination_params
from ..shemas.payment_history_shema import PaymentHistoryPage
from ..shemas.payment_shema import PaymentFilters, PaymentFullRead, CollectionTodayRead
from datetime import datetime
from ...core.clock import today_bogota

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_payment_repository(db: AsyncSession = Depends(get_db)) -> PaymentRepository:
    return PaymentRepository(db)

def get_payment_usecases(repository: PaymentRepository = Depends(get_payment_repository)) -> PaymentUseCases:
    return PaymentUseCases(repository)


@router.get("/", response_model=List[PaymentRead])
async def list_payments(loan_id: Optional[UUID] = Query(None), usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.list_payments(loan_id)

@router.get("/full", response_model=List[PaymentFullRead])
async def list_payments_full(request: Request, usecases: PaymentUseCases = Depends(get_payment_usecases)):
    filters = dict(request.query_params)
    return await usecases.list_payments_full(filters)

@router.get("/today", response_model=List[CollectionTodayRead])
async def get_today_collection(
    route_id: UUID = Query(...),
    date: Optional[str] = Query(None),
    usecases: PaymentUseCases = Depends(get_payment_usecases),
):
    collect_date = datetime.strptime(date, "%Y-%m-%d").date() if date else today_bogota()
    return await usecases.get_today_collection(route_id, collect_date)

@router.get("/history", response_model=PaymentHistoryPage)
async def payment_history(
    loan_id: UUID = Query(...),
    status: Optional[str] = Query(None, pattern="^(pagado|pendiente|mora)$"),
    pagination: PaginationParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    return await PaymentHistoryUseCases(PaymentHistoryRepository(db), user).history(loan_id, status, pagination)

@router.get("/{payment_id}", response_model=Optional[PaymentRead])
async def read_payment(payment_id: UUID, usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.get_payment(payment_id)

@router.post("/", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def create_payment(payment_in: PaymentCreate, usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.create_payment(payment=payment_in)

@router.put("/{payment_id}", response_model=PaymentRead)
async def update_payment(payment_in: PaymentUpdate, usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.update_payment(payment=payment_in)

@router.put("/{payment_id}/pay")
async def pay_payment(
    payment_id: UUID,
    value: float = Query(None),
    usecases: PaymentUseCases = Depends(get_payment_usecases),
    user: UserModel = Depends(get_current_user),
):
    return await usecases.pay_payment(payment_id, value, collected_by=user.id)

@router.delete("/{payment_id}")
async def delete_payment(payment_id: UUID, usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.delete_payment(payment_id)

@router.post("/get_total_liquidation")
async def get_total_liquidation(route_id: UUID, pay_date: str, usecases: PaymentUseCases = Depends(get_payment_usecases)):
    return await usecases.get_total_liquidation(pay_date, route_id)