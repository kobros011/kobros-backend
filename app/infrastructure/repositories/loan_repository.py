from uuid import UUID
from ...domain.entities.loan import Loan
from ...domain.repositories.loan_repository import AbstractLoanRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.loan_model import LoanModel
from ...presentation.shemas.loan_shema import LoanUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException


class LoanRepository(AbstractLoanRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
 
    async def get_loan_by_id(self, loan_id: UUID) -> Optional[Loan]:
        try:
            result = await self.db.execute(
                select(LoanModel).where(LoanModel.id == loan_id)
            )
            model = result.scalars().first()
            if not model:
                raise NotFoundException("Préstamo no encontrado")
            
            return self.model_to_entity(model)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_loans(self) -> List[Loan]:
        try:
            result = await self.db.execute(select(LoanModel))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_loan(self, loan: Loan) -> Optional[Loan]:
        try:
            orm_loan = self.entity_to_model(loan)
            self.db.add(orm_loan)
            await self.db.commit()
            await self.db.refresh(orm_loan)
            return self.model_to_entity(orm_loan)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_loan(self, loan: LoanUpdate) -> Optional[Loan]:
        try:
            result = await self.db.execute(
                select(LoanModel).where(LoanModel.id == loan.id)
            )
            current_loan = result.scalars().first()

            if not current_loan:
                raise NotFoundException("Préstamo no encontrado")

            update_data = loan.model_dump(exclude_unset=True)

            current_loan = self.update_values(update_data, current_model=current_loan)

            await self.db.commit()
            await self.db.refresh(current_loan)
            return self.model_to_entity(current_loan)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def delete_loan(self, loan_id:UUID):
        try:
            result = await self.db.execute(
                select(LoanModel).where(LoanModel.id == loan_id)
            )
            current_user = result.scalars().first()

            if not current_user:
                raise NotFoundException("Préstamo no encontrado")
            
            current_user.active = False

            await self.db.commit()
            await self.db.refresh(current_user)
            return "Préstamo eliminado exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
