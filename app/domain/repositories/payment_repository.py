from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.payment import Payment
from typing import Optional, List
from app.infrastructure.models.payment_model import PaymentModel
from app.presentation.shemas.payment_shema import PaymentFullRead, PaymentFilters, CollectionTodayRead
from datetime import date as date_type
from datetime import datetime

class AbstractPaymentRepository(ABC):
    @abstractmethod
    async def get_payment_by_id(self, payment_id: UUID) -> Optional[Payment]:
        pass

    @abstractmethod
    async def list_payments(self, loan_id: Optional[UUID]) -> List[Payment]:
        pass

    @abstractmethod
    async def list_payments_full(self, filters: PaymentFilters) -> List[PaymentFullRead]:
        pass

    @abstractmethod
    async def pay_payment(self, id: UUID, value: float, collected_by: Optional[UUID] = None):
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

    @abstractmethod
    async def get_total_liquidation(self, pay_date: str, route_id: UUID) -> float:
        pass

    @abstractmethod
    async def list_today_collection(self, route_id: UUID, collect_date: date_type) -> List[CollectionTodayRead]:
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
            applied=model.applied,
            liquidated=model.liquidated,
            date_liquidated=model.date_liquidated,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def model_to_full_read(model: PaymentModel) -> PaymentFullRead:
        return PaymentFullRead(
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
            pending_quotas=model.loan.pending_quotas,
            canceled_quotas=model.loan.canceled_quotas,
            agreed_quotas=model.loan.agreed_quotas,
            total_default=model.loan.total_default,
            value_quota_fixed=model.loan.value_quota_fixed,
            payment_method=model.loan.payment_method,
            value_total_loan=model.loan.value_total_loan,
            client_full_name=model.loan.clientroute.client.full_name,
            client_id=model.loan.clientroute.cliente_id,
            route_id=model.loan.clientroute.route_id,
            date_liquidated=model.date_liquidated,
            applied=model.applied,
            value_capital=model.loan.value_capital,
        )

    @staticmethod
    def model_to_collection_read(model: PaymentModel) -> CollectionTodayRead:
        return CollectionTodayRead(
            id=model.id,
            pay_date=model.pay_date,
            payment_date=model.payment_date,
            quota_number=model.quota_number,
            value=model.value,
            credit_value=model.credit_value,
            status=model.status,
            loan_id=model.loan_id,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            pending_quotas=model.loan.pending_quotas,
            canceled_quotas=model.loan.canceled_quotas,
            agreed_quotas=model.loan.agreed_quotas,
            total_default=model.loan.total_default,
            value_quota_fixed=model.loan.value_quota_fixed,
            payment_method=model.loan.payment_method,
            value_total_loan=model.loan.value_total_loan,
            client_full_name=model.loan.clientroute.client.full_name,
            client_id=model.loan.clientroute.cliente_id,
            route_id=model.loan.clientroute.route_id,
            date_liquidated=model.date_liquidated,
            applied=model.applied,
            value_capital=model.loan.value_capital,
            order=model.loan.clientroute.order,
            id_document=model.loan.clientroute.client.id_document,
            client_address=model.loan.clientroute.client.current_address,
            client_mobile=model.loan.clientroute.client.current_mobile,
            loan_number=model.loan.loan_number,
            client_beak=float(model.loan.clientroute.client.beak or 0),
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
