from uuid import UUID
from ...domain.entities.payment import Payment
from ...domain.repositories.payment_repository import AbstractPaymentRepository
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, select, asc, func, insert
from ..models.payment_model import PaymentModel
from ..models.loan_model import LoanModel
from ..models.route_model import RouteModel
from ..models.client_model import ClientRouteModel
from ..models.client_model import ClientModel
from ...presentation.shemas.payment_shema import PaymentUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import BadRequestException, ConflictException, NotFoundException
from ...core.clock import today_bogota
from ..utils.payment_math import apply_payment_to_quota
from ..utils.Emun import PaymentStatus
from ...presentation.shemas.payment_shema import PaymentFullRead, PaymentFilters, CollectionTodayRead
from datetime import date, datetime
import pytz

bogota_tz = pytz.timezone("America/Bogota")

class PaymentRepository(AbstractPaymentRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stmt_load_more_info(self):
        stmt = select(PaymentModel)

        stmt = (
            stmt
            .join(PaymentModel.loan)
            .join(LoanModel.clientroute)
            .join(ClientRouteModel.client)
        )

        stmt = stmt.options(
            selectinload(PaymentModel.loan)
                .selectinload(LoanModel.clientroute)
                .selectinload(ClientRouteModel.client)
        )

        return stmt

    async def get_stmt(self, filters: PaymentFilters, stmt=None):
        filters_dict = dict(filters)
        text_search = filters_dict.get("text", None)
        status = filters_dict.get("status", None)
        route_id = filters_dict.get("route_id", None)
        pay_date = filters_dict.get("pay_date", None)
        payment_date = filters_dict.get("payment_date", None)
        date_liquidated = filters_dict.get("date_liquidated", None)
        payments_to_pay = filters_dict.get("payments_to_pay", False)
        payments_to_pay_today = filters_dict.get("payments_to_pay_today", False)
        payments_pending = filters_dict.get("payments_pending", False)
        scope_brand = filters_dict.get("_brand_id", None)
        scope_user = filters_dict.get("_assigned_user_id", None)

        if stmt is None:
            stmt = await self.get_stmt_load_more_info()

        if scope_brand or scope_user:
            stmt = stmt.join(RouteModel, RouteModel.id == ClientRouteModel.route_id)
            if scope_brand:
                stmt = stmt.where(RouteModel.brand_id == scope_brand)
            if scope_user:
                stmt = stmt.where(RouteModel.allowed_users_ids.contains([scope_user]))

        if text_search and text_search.strip() and text_search.lower() != "":
            ts = text_search.strip()
            try:
                num = int(ts)
                stmt = stmt.where(
                    or_(
                        ClientModel.full_name.ilike(f"%{ts}%"),
                        ClientModel.id_document.ilike(f"%{ts}%"),
                        LoanModel.loan_number == num
                    )
                )
            except ValueError:
                # no es numérico: solo filtrar por nombre o documento
                stmt = stmt.where(
                    or_(
                        ClientModel.full_name.ilike(f"%{ts}%"),
                        ClientModel.id_document.ilike(f"%{ts}%"),
                    )
                )

        pay_date_dt = None
        if pay_date:
            pay_date_dt = datetime.strptime(pay_date, "%Y-%m-%d").date()
        
        if status:
            status = str(status)
            stmt = stmt.where(PaymentModel.status == status.lower())

        if route_id:
            stmt = stmt.where(ClientRouteModel.route_id == route_id)

        if payment_date:
            payment_date_dt = datetime.strptime(payment_date, "%Y-%m-%d").date()
            stmt = stmt.where(PaymentModel.payment_date == payment_date_dt)

        if date_liquidated:
            date_liquidated_dt = datetime.strptime(date_liquidated, "%Y-%m-%d").date()
            stmt = stmt.where(PaymentModel.date_liquidated == date_liquidated_dt)

        if payments_to_pay and pay_date_dt:
            stmt = stmt.where(PaymentModel.pay_date <= pay_date_dt)

        if payments_to_pay_today and pay_date_dt:
            stmt = stmt.where(PaymentModel.pay_date == pay_date_dt)

        if payments_pending:
            stmt = stmt.where(PaymentModel.liquidated == False)

        return stmt

    async def get_payment_by_id(self, payment_id: UUID) -> Optional[Payment]:
        try:
            result = await self.db.execute(
                select(PaymentModel).where(PaymentModel.id == payment_id)
            )
            model = result.scalars().first()

            if not model:
                raise NotFoundException("El pago no fue encontrado")
            return self.model_to_entity(model)
            
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_payments(self, loan_id: Optional[UUID]) -> List[Payment]:
        try:
            stmt = select(PaymentModel)
            
            if loan_id:
                stmt = stmt.where(PaymentModel.loan_id == loan_id).order_by(asc(PaymentModel.quota_number))

            result = await self.db.execute(stmt)
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_payments_full(self, filters: PaymentFilters) -> List[PaymentFullRead]:
        try:
            stmt = await self.get_stmt_load_more_info()
            stmt = await self.get_stmt(filters, stmt)
            stmt = stmt.order_by(asc(ClientRouteModel.order))

            result = await self.db.execute(stmt)
            models = result.scalars().all()
            return [self.model_to_full_read(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def create_payment(self, payment: Payment) -> Optional[Payment]:
        try:
            orm_payment = self.entity_to_model(payment)
            self.db.add(orm_payment)
            await self.db.commit()
            await self.db.refresh(orm_payment)
            return self.model_to_entity(orm_payment)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def bulk_create_payments(self, rows: List[dict]) -> None:
        """Inserta todas las cuotas en una sola sentencia. No hace commit: lo decide el llamador (transacción del crédito)."""
        if rows:
            await self.db.execute(insert(PaymentModel), rows)

    async def update_payment(self, payment: PaymentUpdate) -> Optional[Payment]:
        try:
            result = await self.db.execute(
                select(PaymentModel).where(PaymentModel.id == payment.id)
            )
            current_payment = result.scalars().first()

            if not current_payment:
                raise NotFoundException("El pago no fue encontrado")

            update_data = payment.model_dump(exclude_unset=True)

            current_payment = self.update_values(update_data, current_model=current_payment)

            await self.db.commit()
            await self.db.refresh(current_payment)
            return self.model_to_entity(current_payment)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        
    async def pay_payment(self, id: UUID, value: float, collected_by: Optional[UUID] = None):
        try:
            stmt = (
                select(PaymentModel)
                .where(PaymentModel.id == id)
                .join(PaymentModel.loan)
                .join(LoanModel.clientroute)
                .join(ClientRouteModel.client)
                .options(
                    selectinload(PaymentModel.loan)
                        .selectinload(LoanModel.clientroute)
                        .selectinload(ClientRouteModel.client)
                )
            )

            result = await self.db.execute(stmt)
            current_payment: PaymentModel = result.scalars().first()

            if not current_payment:
                raise NotFoundException("El pago no fue encontrado")
            
            loan: LoanModel = current_payment.loan
            client_route: ClientRouteModel = loan.clientroute
            client: ClientModel = client_route.client

            applied = float(current_payment.applied or 0)
            value = float(value or 0)

            # Solo se abona una cuota que vence hoy o ya venció, y que aún tiene saldo.
            if current_payment.pay_date and current_payment.pay_date > today_bogota():
                raise BadRequestException("La cuota aún no vence, no se puede abonar")
            if applied >= float(current_payment.value or 0) - 0.01:
                raise BadRequestException("La cuota ya está pagada")
            apply_payment_to_quota(current_payment, loan, client, value, today_bogota(), collected_by)

            await self.db.commit()

            await self.db.refresh(current_payment)
            await self.db.refresh(loan)
            await self.db.refresh(client)

            return self.model_to_entity(current_payment)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_today_collection(self, route_id: UUID, collect_date: date) -> list[CollectionTodayRead]:
        try:
            stmt = await self.get_stmt_load_more_info()
            stmt = stmt.where(
                ClientRouteModel.route_id == route_id,
                PaymentModel.liquidated == False,
                or_(
                    and_(
                        PaymentModel.status != PaymentStatus.paid.value,
                        PaymentModel.pay_date <= collect_date,
                    ),
                    and_(
                        PaymentModel.status == PaymentStatus.paid.value,
                        PaymentModel.payment_date == collect_date,
                    ),
                ),
            ).order_by(asc(ClientRouteModel.order))
            result = await self.db.execute(stmt)
            models = result.scalars().all()
            return [self.model_to_collection_read(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def delete_payment(self, payment_id:UUID):
        try:
            result = await self.db.execute(
                select(PaymentModel).where(PaymentModel.id == payment_id)
            )
            current_payment = result.scalars().first()

            if not current_payment:
                raise NotFoundException("El pago no fue encontrado")
            
            current_payment.active = False

            await self.db.commit()
            await self.db.refresh(current_payment)
            return "Pago eliminado exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

