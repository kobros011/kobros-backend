from uuid import UUID
from ...domain.entities.loan import Loan
from ...domain.repositories.loan_repository import AbstractLoanRepository
from sqlalchemy import select, or_, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List
from ..models.loan_model import LoanModel
from ..models.client_route_model import ClientRouteModel
from ..models.client_model import ClientModel
from ...presentation.shemas.loan_shema import LoanUpdate, LoanCreate, LoansFilters
from ...presentation.shemas.client_shema import ClientUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException
from .client_route_repository import ClientRouteRepository
from .client_repository import ClientRepository
from .payment_repository import PaymentRepository
from .route_repository import RouteRepository
from datetime import datetime

class LoanRepository(AbstractLoanRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
 
    async def get_loan_by_id(self, loan_id: UUID) -> Optional[Loan]:
        try:
            stmt = select(LoanModel).where(LoanModel.id == loan_id)
            stmt = (
                stmt
                .join(LoanModel.clientroute)
                .join(ClientRouteModel.route)
                .join(ClientRouteModel.client)
            )

            stmt = stmt.options(
                selectinload(LoanModel.clientroute)
                    .selectinload(ClientRouteModel.route),
                selectinload(LoanModel.clientroute)
                    .selectinload(ClientRouteModel.client)
            )

            result = await self.db.execute(stmt)
            model = result.scalars().first()
            
            if not model:
                raise NotFoundException("Préstamo no encontrado")
            
            return self.model_to_entity_full(model)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def get_loans_by_params(self, params: LoansFilters) -> List[Loan]:
        try:
            filters_dict = dict(params)
            text_search = filters_dict.get("text", None)
            route_id = filters_dict.get("route_id", None)
            initial_date = filters_dict.get("initial_date", None)
            end_date = filters_dict.get("end_date", None)
            payment_method = filters_dict.get("payment_method", None)

            stmt = select(LoanModel)
            stmt = (
                stmt
                .join(LoanModel.clientroute)
                .join(ClientRouteModel.route)
                .join(ClientRouteModel.client)
            )

            stmt = stmt.options(
                selectinload(LoanModel.clientroute)
                    .selectinload(ClientRouteModel.route),
                selectinload(LoanModel.clientroute)
                    .selectinload(ClientRouteModel.client)
            )

            if text_search and text_search.strip() and text_search.lower() != "":
                ts = text_search.strip().lower()
                try:
                    num = int(ts)
                    stmt = stmt.where(
                        or_(
                            LoanModel.loan_number == num,
                            ClientModel.id_document.ilike(f"%{ts}%"),
                            ClientModel.full_name.ilike(f"%{ts}%"),
                        )
                    )
                except ValueError:
                    stmt = stmt.where(
                        or_(
                            ClientModel.full_name.ilike(f"%{ts}%"),
                            ClientModel.id_document.ilike(f"%{ts}%"),
                        )
                    )
                        

            if route_id:
                stmt = stmt.where(ClientRouteModel.route_id == route_id)

            if initial_date and end_date and initial_date != '' and end_date != '':
                
                initial_dt = datetime.strptime(initial_date, "%Y-%m-%d").date()
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

                stmt = stmt.where(
                    or_(
                        LoanModel.initial_date.between(initial_dt, end_dt),
                        LoanModel.end_date.between(initial_dt, end_dt),
                    )
                )

            if payment_method:
                stmt = stmt.where(LoanModel.payment_method == payment_method)

            return stmt
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_loans(self, filters: LoansFilters) -> List[Loan]:
        try:

            query_stmt = await self.get_loans_by_params(params=filters)

            result = await self.db.execute(query_stmt)
            models = result.scalars().all()

            return [self.model_to_entity_full(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_loan(self, loan: LoanCreate) -> Optional[Loan]:
        try:
            if loan.new_order:
                await ClientRouteRepository.update_multiples_orders(self=self, current_client_route_id=loan.clientroute_id, new_order=loan.new_order)

            await ClientRepository.update_client(self=ClientRepository(self.db), client=ClientUpdate(id=loan.client_id, current_address=loan.current_address, current_mobile=loan.current_mobile))

            orm_loan = self.entity_to_model(Loan(**loan.model_dump(exclude=["current_address", "current_mobile", "client_id", "new_order"]), pending_quotas=loan.agreed_quotas))

            self.db.add(orm_loan)
            await self.db.commit()
            await self.db.refresh(orm_loan)

            client_route = await ClientRouteRepository.get_client_route_by_id(self=ClientRouteRepository(self.db), client_route_id=loan.clientroute_id)
            await RouteRepository.update_loan_number(self=RouteRepository(self.db), route_id=getattr(client_route, 'route_id'), new_loan_number=loan.loan_number)

            await PaymentRepository.create_multiple_payments(self=PaymentRepository(self.db), loan=loan, loan_id=orm_loan.id)

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
