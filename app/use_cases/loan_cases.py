from uuid import UUID
from typing import Optional, List
from ..domain.repositories.loan_repository import AbstractLoanRepository
from ..domain.entities.loan import Loan, LoanFull
from ..presentation.shemas.loan_shema import LoanCreate, LoanUpdate, LoansFilters

class LoanUseCases:
    def __init__(self, repository: AbstractLoanRepository):
        self.repository = repository

    async def get_loan(self, loan_id: UUID) -> Optional[LoanFull]:
        return await self.repository.get_loan_by_id(loan_id)
    
    async def list_loans(self, filters: LoansFilters) -> List[LoanFull]:
        return await self.repository.list_loans(filters)
    
    async def create_loan(self, loan: LoanCreate) -> Optional[Loan]:
        return await self.repository.create_loan(loan)
    
    async def update_loan(self, loan: LoanUpdate) -> Optional[Loan]:
        return await self.repository.update_loan(loan)
    
    async def delete_loan(self, loan_id: UUID):
        return await self.repository.delete_loan(loan_id)
