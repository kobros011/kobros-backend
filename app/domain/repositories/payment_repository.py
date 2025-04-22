from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.payment import Payment
from typing import Optional, List
from app.infrastructure.models.payment_model import PaymentModel


class AbstractPaymentRepository(ABC):
    @abstractmethod
    async def get_payment_by_id(self, payment_id: UUID) -> Optional[Payment]:
        pass

    @abstractmethod
    async def list_payments(self) -> List[Payment]:
        pass

    @abstractmethod
    async def create_payment(self, payment: Payment) -> Optional[Payment]:
        pass

    @abstractmethod
    async def update_payment(self, payment: Payment) -> Optional[Payment]:
        pass

    @abstractmethod
    async def delete_payment(self, payment_id: UUID):
        pass
    
    @staticmethod
    def model_to_entity(model: PaymentModel) -> Payment:
        return Payment( 
            id=model.id,
            pay_date=model.pay_date,
            payment_date=model.payment_date,
            quota_number=model.quota_number,
            value=model.value,
            credit_value=model.credit_value,
            status=model.status,
            loan_id= model.loan_id,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def entity_to_model(entity: Payment) -> PaymentModel:
        return PaymentModel(
            id=entity.id,
            pay_date=entity.pay_date,
            payment_date=entity.payment_date,
            quota_number=entity.quota_number,
            value=entity.value,
            credit_value=entity.credit_value,
            status=entity.status,
            loan_id= entity.loan_id,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def update_values(update_data: dict[str, any], current_model: PaymentModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model
