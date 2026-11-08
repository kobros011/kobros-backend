from uuid import UUID
from typing import Optional, List
from ..domain.repositories.payment_repository import AbstractPaymentRepository
from ..domain.entities.payment import Payment
from ..presentation.shemas.payment_shema import PaymentCreate, PaymentUpdate, PaymentFilters, PaymentFullRead, CollectionTodayRead
from datetime import datetime, date

class PaymentUseCases:
    def __init__(self, repository: AbstractPaymentRepository):
        self.repository = repository

    async def get_payment(self, payment_id: UUID) -> Optional[Payment]:
        return await self.repository.get_payment_by_id(payment_id)
    
    async def list_payments(self, loan_id: Optional[UUID]) -> List[Payment]:
        return await self.repository.list_payments(loan_id)
    
    async def list_payments_full(self, filters: PaymentFilters) -> List[PaymentFullRead]:
        return await self.repository.list_payments_full(filters)
    
    async def pay_payment(self, id: UUID, value: float, collected_by: Optional[UUID] = None):
        return await self.repository.pay_payment(id=id, value=value, collected_by=collected_by)
    
    async def create_payment(self, payment: PaymentCreate) -> Optional[Payment]:
        new_payment = Payment(**payment.model_dump())
        return await self.repository.create_payment(new_payment)
    
    async def update_payment(self, payment: PaymentUpdate) -> Optional[Payment]:
        return await self.repository.update_payment(payment)
    
    async def delete_payment(self, payment_id: UUID):
        return await self.repository.delete_payment(payment_id)
    async def get_today_collection(self, route_id: UUID, collect_date: date) -> List[CollectionTodayRead]:
        return await self.repository.list_today_collection(route_id, collect_date)