from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.loan import Loan
from typing import Optional, List
from app.infrastructure.models.loan_model import LoanModel


class AbstractLoanRepository(ABC):
    @abstractmethod
    async def get_loan_by_id(self, loan_id: UUID) -> Optional[Loan]:
        pass

    @abstractmethod
    async def list_loans(self) -> List[Loan]:
        pass

    @abstractmethod
    async def create_loan(self, loan: Loan) -> Optional[Loan]:
        pass

    @abstractmethod
    async def update_loan(self, loan: Loan) -> Optional[Loan]:
        pass

    @abstractmethod
    async def delete_loan(self, loan_id: UUID):
        pass

    @staticmethod
    def model_to_entity(model: LoanModel) -> Loan:
        return Loan(
            id=model.id,
            loan_number=model.loan_number,
            initial_date=model.initial_date,
            end_date=model.end_date,
            value_quota_fixed=model.value_quota_fixed,
            agreed_quotas=model.agreed_quotas,
            date_first_quota=model.date_first_quota,
            payment_method=model.payment_method,
            value_capital=model.value_capital,
            value_utility_loan=model.value_utility_loan,
            value_total_loan=model.value_total_loan,
            interest_rate=model.interest_rate,
            clientroute_id=model.clientroute_id,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def entity_to_model(entity: Loan) -> LoanModel:
        return LoanModel(
            id=entity.id,
            loan_number=entity.loan_number,
            initial_date=entity.initial_date,
            end_date=entity.end_date,
            value_quota_fixed=entity.value_quota_fixed,
            agreed_quotas=entity.agreed_quotas,
            date_first_quota=entity.date_first_quota,
            payment_method=entity.payment_method,
            value_capital=entity.value_capital,
            value_utility_loan=entity.value_utility_loan,
            value_total_loan=entity.value_total_loan,
            interest_rate=entity.interest_rate,
            clientroute_id=entity.clientroute_id,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def update_values(update_data: dict[str, any], current_model: LoanModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model
