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


# ---- rutas, clientes, marcas, conceptos (mismo criterio: dev libre; resto, su marca; 04/05, rutas asignadas) ----

def _route_visible(route_brand, allowed, user: UserModel) -> bool:
    role = _role(user)
    if role != "01" and user.brand_id != route_brand:
        return False
    if role in ("04", "05") and user.id not in (allowed or []):
        return False
    return True


async def ensure_route_access(db: AsyncSession, route_id: UUID, user: UserModel) -> None:
    row = (await db.execute(select(RouteModel.brand_id, RouteModel.allowed_users_ids).where(RouteModel.id == route_id))).first()
    if row is None or not _route_visible(row.brand_id, row.allowed_users_ids, user):
        raise NotFoundException("Ruta no encontrada")


async def ensure_client_access(db: AsyncSession, client_id: UUID, user: UserModel) -> None:
    from app.infrastructure.models.client_model import ClientModel
    brand_id = (await db.execute(select(ClientModel.brand_id).where(ClientModel.id == client_id))).scalar_one_or_none()
    role = _role(user)
    if brand_id is None and (await db.execute(select(ClientModel.id).where(ClientModel.id == client_id))).first() is None:
        raise NotFoundException("El cliente no fue encontrado")
    if role != "01" and user.brand_id != brand_id:
        raise NotFoundException("El cliente no fue encontrado")
    if role in ("04", "05"):
        routes = (await db.execute(
            select(RouteModel.allowed_users_ids).join(ClientRouteModel, ClientRouteModel.route_id == RouteModel.id)
            .where(ClientRouteModel.cliente_id == client_id)
        )).scalars().all()
        if not any(user.id in (allowed or []) for allowed in routes):
            raise NotFoundException("El cliente no fue encontrado")


async def ensure_clientroute_access(db: AsyncSession, client_route_id: UUID, user: UserModel) -> None:
    route_id = (await db.execute(select(ClientRouteModel.route_id).where(ClientRouteModel.id == client_route_id))).scalar_one_or_none()
    if route_id is None:
        raise NotFoundException("Orden del cliente no encontrado")
    await ensure_route_access(db, route_id, user)


def ensure_brand_access(brand_id: UUID, user: UserModel) -> None:
    if _role(user) != "01" and user.brand_id != brand_id:
        raise NotFoundException("Marca no encontrada")


async def ensure_concept_access(db: AsyncSession, concept_id: UUID, user: UserModel) -> None:
    from app.infrastructure.models.expense_model import ExpenseConceptModel
    brand_id = (await db.execute(select(ExpenseConceptModel.brand_id).where(ExpenseConceptModel.id == concept_id))).scalar_one_or_none()
    if brand_id is None or (_role(user) != "01" and user.brand_id != brand_id):
        raise NotFoundException("Concepto no encontrado")
