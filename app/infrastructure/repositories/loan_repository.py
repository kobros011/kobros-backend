from app.infrastructure.utils.access import ROUTE_SCOPED_ROLES
from uuid import UUID
from ...domain.entities.loan import Loan
from ...domain.repositories.loan_repository import AbstractLoanRepository
from sqlalchemy import select, or_, and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List
from ..models.loan_model import LoanModel
from ..models.payment_model import PaymentModel
from ..models.client_route_model import ClientRouteModel
from ..models.client_model import ClientModel
from ...presentation.shemas.loan_shema import LoanUpdate, LoanCreate, LoansFilters
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException
from ...core.pagination import PaginationParams, paginate_or_all
from .client_route_repository import ClientRouteRepository
from .payment_repository import PaymentRepository
from .route_repository import RouteRepository
from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4
import pytz
from ...core.clock import today_bogota
from ...core.exceptions import BadRequestException, ForbiddenException
from ..models.route_model import RouteModel
from ..models.user_model import UserModel
from ..utils.Emun import PaymentStatus
from ..utils.payment_math import apply_payment_to_quota
from ..utils.timedelta_pay_date import build_payment_schedule

_BOGOTA = pytz.timezone("America/Bogota")


def _to_bogota_date(value: datetime) -> date:
    """Fecha calendario en Colombia: el front envía ISO en UTC y desde las 19:00 ya sería el día siguiente."""
    if value.tzinfo is not None:
        value = value.astimezone(_BOGOTA)
    return value.date()

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
            

            entity = self.model_to_entity_full(model)
            # Mismas definiciones que Reportes/Cartera (loan_stats): pagado = Σ applied, saldo = total − pagado.
            entity.paid = float((await self.db.execute(
                select(func.coalesce(func.sum(PaymentModel.applied), 0)).where(PaymentModel.loan_id == loan_id)
            )).scalar_one())
            entity.balance = float(model.value_total_loan or 0) - entity.paid
            return entity
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
            client_id = filters_dict.get("client_id", None)
            scope_brand = filters_dict.get("_brand_id", None)
            scope_user = filters_dict.get("_assigned_user_id", None)

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

            if client_id:
                stmt = stmt.where(ClientRouteModel.cliente_id == client_id)

            if scope_brand:
                stmt = stmt.where(RouteModel.brand_id == scope_brand)
            if scope_user:
                stmt = stmt.where(RouteModel.allowed_users_ids.contains([scope_user]))

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

    async def list_loans(self, filters: LoansFilters, params: Optional[PaginationParams] = None) -> tuple[List[Loan], int]:
        try:
            query_stmt = (await self.get_loans_by_params(params=filters)).order_by(
                LoanModel.created_at.desc().nulls_last(), LoanModel.id.desc()
            )
            return await paginate_or_all(self.db, query_stmt, params, self.model_to_entity_full)
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_loan(self, loan: LoanCreate, user: UserModel) -> Optional[Loan]:
        """Crea el crédito y todas sus cuotas en UNA transacción (un solo commit, inserción en lote).

        El servidor es la fuente de verdad de los cálculos y del número de crédito; el cobro inicial
        (`value_payment`) se aplica a la cuota 1 con la misma regla que un abono.
        """
        try:
            orm_loan = await self.create_loan_in_tx(loan, user)
            await self.db.commit()
            await self.db.refresh(orm_loan)  # created_at/updated_at los pone la BD
            return self.model_to_entity(orm_loan)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)
        except Exception:
            await self.db.rollback()
            raise

    async def create_loan_in_tx(self, loan: LoanCreate, user: UserModel) -> LoanModel:
        """Núcleo de la creación SIN commit ni rollback: lo usa también la creación de un cliente con su primer crédito."""
        today = today_bogota()
        first_date = _to_bogota_date(loan.date_first_quota)
        schedule = build_payment_schedule(first_date, loan.payment_method, loan.agreed_quotas, loan.fixed_payment_day)
        if loan.value_payment and schedule[0] > today:
            raise BadRequestException(
                f"La primera cuota vence el {schedule[0]:%d/%m/%Y}: no se puede registrar un cobro inicial antes de esa fecha")

        # Una consulta: cliente-ruta + ruta (bloqueada para numerar sin carreras) + cliente.
        row = (await self.db.execute(
            select(ClientRouteModel, RouteModel, ClientModel)
            .join(RouteModel, RouteModel.id == ClientRouteModel.route_id)
            .join(ClientModel, ClientModel.id == ClientRouteModel.cliente_id)
            .where(ClientRouteModel.id == loan.clientroute_id)
            .with_for_update(of=RouteModel)
        )).first()
        if row is None:
            raise NotFoundException("Orden del cliente no encontrado")
        client_route, route, client = row
        self._authorize(user, route, client_route, loan.client_id)

        if loan.new_order:
            await ClientRouteRepository.update_multiples_orders(
                self=self, current_client_route_id=loan.clientroute_id, new_order=loan.new_order, commit=False)
        client.current_address = loan.current_address
        client.current_mobile = loan.current_mobile

        total = round(loan.value_quota_fixed * loan.agreed_quotas, 2)
        utility = round(total - loan.value_capital, 2)
        route.loans_number = int(route.loans_number or 0) + 1
        orm_loan = LoanModel(
            loan_number=route.loans_number,
            initial_date=_to_bogota_date(loan.initial_date),
            end_date=schedule[-1],
            date_first_quota=first_date,
            value_quota_fixed=loan.value_quota_fixed,
            agreed_quotas=loan.agreed_quotas,
            payment_method=loan.payment_method,
            fixed_payment_day=loan.fixed_payment_day,
            value_capital=loan.value_capital,
            value_utility_loan=utility,
            value_total_loan=total,
            interest_rate=round(utility / loan.value_capital * 100, 4),
            pending_quotas=loan.agreed_quotas,
            canceled_quotas=0,
            total_default=0,
            clientroute_id=loan.clientroute_id,
            created_by=user.id,
        )
        self.db.add(orm_loan)
        await self.db.flush()

        rows = [
            {
                "id": uuid4(), "loan_id": orm_loan.id, "quota_number": i + 1, "pay_date": pay_date,
                "value": loan.value_quota_fixed, "credit_value": total, "status": PaymentStatus.pending.value, "active": True,
                # Mismas columnas en todas las filas: así el INSERT va en una sola sentencia.
                "applied": None, "payment_date": None, "collected_by": None,
            }
            for i, pay_date in enumerate(schedule)
        ]
        if loan.value_payment:
            first = SimpleNamespace(**rows[0])
            apply_payment_to_quota(first, orm_loan, client, loan.value_payment, today, user.id)
            rows[0] = dict(vars(first))
        await PaymentRepository(self.db).bulk_create_payments(rows)
        return orm_loan

    @staticmethod
    def _authorize(user: UserModel, route: RouteModel, client_route: ClientRouteModel, client_id: UUID) -> None:
        """Marca del usuario = marca de la ruta (dev sin restricción); socio/recaudador solo en rutas donde están asignados."""
        if client_route.cliente_id != client_id:
            raise BadRequestException("El cliente no pertenece a esa ruta")
        role = user.type_user.value if hasattr(user.type_user, "value") else str(user.type_user)
        if role != "01" and user.brand_id != route.brand_id:
            raise NotFoundException("Orden del cliente no encontrado")
        if role in ROUTE_SCOPED_ROLES and user.id not in (route.allowed_users_ids or []):
            raise ForbiddenException("No tienes asignada esta ruta")

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
