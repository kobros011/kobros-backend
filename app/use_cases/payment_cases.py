from uuid import UUID
from typing import Optional, List
from ..domain.repositories.payment_repository import AbstractPaymentRepository
from ..domain.entities.payment import Payment
from ..presentation.shemas.payment_shema import PaymentCreate, PaymentUpdate

class PaymentUseCases:
    def __init__(self, repository: AbstractPaymentRepository):
        self.repository = repository

    async def get_payment(self, payment_id: UUID) -> Optional[Payment]:
        return await self.repository.get_payment_by_id(payment_id)
    
    async def list_payments(self) -> List[Payment]:
        return await self.repository.list_payments()
    
    async def create_payment(self, payment: PaymentCreate) -> Optional[Payment]:
        new_payment = Payment(**payment.model_dump())
        return await self.repository.create_payment(new_payment)
    
    async def update_payment(self, payment: PaymentUpdate) -> Optional[Payment]:
        return await self.repository.update_payment(payment)
    
    async def delete_payment(self, payment_id: UUID):
        return await self.repository.delete_payment(payment_id)