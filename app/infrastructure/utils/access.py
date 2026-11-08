"""Alcance por marca y ruta para recursos que se piden por id (crédito, pago).

Regla única (la misma de liquidaciones y créditos): el dev (01) ve todo; el resto, solo recursos de su marca; el socio (04) y el
cobrador (05), además, solo de las rutas donde están asignados. Si no cumple, responde 404 (no revela que existe).
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.infrastructure.models.client_route_model import ClientRouteModel
from app.infrastructure.models.loan_model import LoanModel
from app.infrastructure.models.payment_model import PaymentModel
from app.infrastructure.models.route_model import RouteModel
from app.infrastructure.models.user_model import UserModel


def _role(user: UserModel) -> str:
    return user.type_user.value if hasattr(user.type_user, "value") else str(user.type_user)


async def ensure_loan_access(db: AsyncSession, loan_id: UUID, user: UserModel) -> None:
    row = (await db.execute(
        select(RouteModel.brand_id, RouteModel.allowed_users_ids)
        .select_from(LoanModel)
        .join(ClientRouteModel, ClientRouteModel.id == LoanModel.clientroute_id)
        .join(RouteModel, RouteModel.id == ClientRouteModel.route_id)
        .where(LoanModel.id == loan_id)
    )).first()
    if row is None:
        raise NotFoundException("Préstamo no encontrado")
    role = _role(user)
    if role != "01" and user.brand_id != row.brand_id:
        raise NotFoundException("Préstamo no encontrado")
    if role in ("04", "05") and user.id not in (row.allowed_users_ids or []):
        raise NotFoundException("Préstamo no encontrado")


async def ensure_payment_access(db: AsyncSession, payment_id: UUID, user: UserModel) -> None:
    loan_id = (await db.execute(select(PaymentModel.loan_id).where(PaymentModel.id == payment_id))).scalar_one_or_none()
    if loan_id is None:
        raise NotFoundException("El pago no fue encontrado")
    await ensure_loan_access(db, loan_id, user)
