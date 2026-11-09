from app.infrastructure.utils.access import ROUTE_SCOPED_ROLES
from uuid import UUID
from typing import Optional, List
from ..core.pagination import PaginationParams, page_or_list
from ..domain.repositories.loan_repository import AbstractLoanRepository
from ..domain.entities.loan import Loan, LoanFull
from ..presentation.shemas.loan_shema import LoanCreate, LoanUpdate, LoansFilters

class LoanUseCases:
    def __init__(self, repository: AbstractLoanRepository):
        self.repository = repository

    async def get_loan(self, loan_id: UUID) -> Optional[LoanFull]:
        return await self.repository.get_loan_by_id(loan_id)
    
    async def list_loans(self, filters: LoansFilters, params: Optional[PaginationParams] = None, user=None):
        # Alcance: marca del usuario (dev sin restricción); socio y cobrador, solo rutas donde están asignados.
        if user is not None:
            role = user.type_user.value if hasattr(user.type_user, "value") else str(user.type_user)
            scoped = dict(filters)
            if role != "01":
                scoped["_brand_id"] = user.brand_id
            if role in ROUTE_SCOPED_ROLES:
                scoped["_assigned_user_id"] = user.id
            filters = scoped
        items, total = await self.repository.list_loans(filters, params)
        return page_or_list(items, total, params)
    
    async def create_loan(self, loan: LoanCreate, user) -> Optional[Loan]:
        return await self.repository.create_loan(loan, user)
    
    async def update_loan(self, loan: LoanUpdate) -> Optional[Loan]:
        return await self.repository.update_loan(loan)
    
    async def delete_loan(self, loan_id: UUID):
        return await self.repository.delete_loan(loan_id)
