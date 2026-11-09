"""Cifras de un cierre de caja, calculadas siempre con SUM/COUNT en SQL (fuente única).

Las usan la vista previa, el cierre y la detección de "cierre desactualizado", así que los tres coinciden. Base de cálculo:

* recaudo   = Σ `applied` de pagos con `payment_date == día` (lo realmente cobrado ese día, sin importar el vencimiento),
              de la ruta, activos y, si hay cobrador, con `collected_by == cobrador`.
* meta      = Σ valor de las cuotas de la ruta que vencen ese día.
* gastos    = Σ gastos activos de la ruta de ese día (de quien los creó, si hay cobrador).
* créditos  = Σ capital de los créditos creados ese día (en hora de Bogotá) por el cobrador (o toda la ruta si es consolidado).
* esperado  = base entregada + recaudo − gastos − créditos nuevos;  diferencia = efectivo entregado − esperado.

Cada pago/gasto pertenece a un solo cierre (`liquidation_id`). Un cobro hecho después del cierre queda sin enlazar y por
eso se detecta como diferencia entre lo guardado y lo vigente.
"""
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.client_route_model import ClientRouteModel
from ..models.client_model import ClientModel
from ..models.expense_model import ExpenseConceptModel, ExpenseModel
from ..models.loan_model import LoanModel
from ..models.payment_model import PaymentModel
from ..models.user_model import UserModel

BOGOTA_TZ = "America/Bogota"
TOLERANCE = 0.01


def _unliquidated(column, liquidation_id: Optional[UUID]):
    """Sin cierre, o incluido en `liquidation_id` (para comparar un cierre existente con lo vigente)."""
    return or_(column.is_(None), column == liquidation_id) if liquidation_id else column.is_(None)


def payment_conditions(route_id: UUID, day: date, collector_id: Optional[UUID], liquidation_id: Optional[UUID] = None) -> list:
    conditions = [
        ClientRouteModel.route_id == route_id,
        PaymentModel.active.is_(True),
        PaymentModel.payment_date == day,
        func.coalesce(PaymentModel.applied, 0) > 0,
        _unliquidated(PaymentModel.liquidation_id, liquidation_id),
    ]
    if collector_id:
        conditions.append(PaymentModel.collected_by == collector_id)
    return conditions


def expense_conditions(route_id: UUID, day: date, collector_id: Optional[UUID], liquidation_id: Optional[UUID] = None) -> list:
    conditions = [
        ExpenseModel.route_id == route_id,
        ExpenseModel.active.is_(True),
        ExpenseModel.date == day,
        _unliquidated(ExpenseModel.liquidation_id, liquidation_id),
    ]
    if collector_id:
        conditions.append(ExpenseModel.created_by == collector_id)
    return conditions


def _payments_from(stmt):
    return stmt.select_from(PaymentModel).join(LoanModel, LoanModel.id == PaymentModel.loan_id).join(
        ClientRouteModel, ClientRouteModel.id == LoanModel.clientroute_id)


def loan_conditions_for(route_id: UUID, day: date, collector_id: Optional[UUID]) -> list:
    """Créditos creados ese día (hora de Bogotá) en la ruta. Se muestran todos, sin importar quién los creó:
    el dinero salió de la caja de la ruta ese día, la afecte o no el cobrador que liquida."""
    return [ClientRouteModel.route_id == route_id, LoanModel.active.is_(True), func.date(func.timezone(BOGOTA_TZ, LoanModel.created_at)) == day]


async def compute_figures(db: AsyncSession, route_id: UUID, day: date, collector_id: Optional[UUID], liquidation_id: Optional[UUID] = None) -> dict:
    applied = func.coalesce(PaymentModel.applied, 0)
    value = func.coalesce(PaymentModel.value, 0)

    paid = (await db.execute(_payments_from(select(
        func.coalesce(func.sum(applied), 0).label("total"),
        func.count().label("receipts"),
        func.coalesce(func.sum(applied).filter(PaymentModel.pay_date == day), 0).label("due_today"),
        func.coalesce(func.sum(applied).filter(PaymentModel.pay_date < day), 0).label("overdue"),
        func.count().filter(applied < value - TOLERANCE).label("partial"),
        func.coalesce(func.sum(func.greatest(applied - value, 0)), 0).label("beak"),
    )).where(*payment_conditions(route_id, day, collector_id, liquidation_id)))).mappings().one()

    goal = (await db.execute(_payments_from(select(func.coalesce(func.sum(value), 0))).where(
        ClientRouteModel.route_id == route_id, PaymentModel.active.is_(True), PaymentModel.pay_date == day))).scalar_one()

    spent = (await db.execute(select(func.coalesce(func.sum(ExpenseModel.value), 0)).where(
        *expense_conditions(route_id, day, collector_id, liquidation_id)))).scalar_one()

    loan_conditions = loan_conditions_for(route_id, day, collector_id)
    loans = (await db.execute(select(
        func.coalesce(func.sum(LoanModel.value_capital), 0).label("total"), func.count().label("count"),
    ).select_from(LoanModel).join(ClientRouteModel, ClientRouteModel.id == LoanModel.clientroute_id).where(*loan_conditions))).mappings().one()

    return {
        "goal": float(goal),
        "collected_total": float(paid["total"]),
        "receipts_count": int(paid["receipts"]),
        "collected_due_today": float(paid["due_today"]),
        "collected_overdue": float(paid["overdue"]),
        "partial_count": int(paid["partial"]),
        "beak_generated": float(paid["beak"]),
        "expenses_total": float(spent),
        "new_loans_total": float(loans["total"]),
        "new_loans_count": int(loans["count"]),
    }


def expected_cash(base: float, figures: dict) -> float:
    return round(base + figures["collected_total"] - figures["expenses_total"] - figures["new_loans_total"], 2)


async def expense_lines(db: AsyncSession, route_id: UUID, day: date, collector_id: Optional[UUID], liquidation_id: Optional[UUID] = None) -> list[dict]:
    rows = (await db.execute(
        select(ExpenseModel.id, ExpenseModel.name, ExpenseModel.value, ExpenseConceptModel.concept.label("concept"))
        .outerjoin(ExpenseConceptModel, ExpenseConceptModel.id == ExpenseModel.expensesconcept_id)
        .where(*expense_conditions(route_id, day, collector_id, liquidation_id)).order_by(ExpenseModel.created_at)
    )).mappings().all()
    return [dict(r) for r in rows]


async def payment_lines(db: AsyncSession, route_id: UUID, day: date, collector_id: Optional[UUID], liquidation_id: Optional[UUID] = None) -> list[dict]:
    rows = (await db.execute(
        _payments_from(select(
            PaymentModel.id, PaymentModel.quota_number, PaymentModel.pay_date, PaymentModel.applied, PaymentModel.value,
            LoanModel.loan_number, ClientModel.full_name.label("client_name"),
        )).join(ClientModel, ClientModel.id == ClientRouteModel.cliente_id)
        .where(*payment_conditions(route_id, day, collector_id, liquidation_id)).order_by(PaymentModel.updated_at)
    )).mappings().all()
    return [dict(r) for r in rows]


async def new_loan_lines(db: AsyncSession, route_id: UUID, day: date, collector_id: Optional[UUID], hide_creator_for: Optional[UUID] = None) -> list[dict]:
    """`hide_creator_for`: un cobrador viendo su propia caja no necesita ver su propio nombre como creador,
    solo el de alguien más (admin/súper siempre ven el nombre, por eso pasan None)."""
    rows = (await db.execute(
        select(LoanModel.id, LoanModel.loan_number, LoanModel.value_capital, LoanModel.value_total_loan, LoanModel.agreed_quotas,
               LoanModel.value_quota_fixed, LoanModel.payment_method, ClientModel.full_name.label("client_name"),
               LoanModel.created_by, UserModel.full_name.label("created_by_name"))
        .select_from(LoanModel).join(ClientRouteModel, ClientRouteModel.id == LoanModel.clientroute_id)
        .join(ClientModel, ClientModel.id == ClientRouteModel.cliente_id)
        .outerjoin(UserModel, UserModel.id == LoanModel.created_by)
        .where(*loan_conditions_for(route_id, day, collector_id)).order_by(LoanModel.created_at)
    )).mappings().all()
    return [{**r, "value_capital": float(r["value_capital"] or 0), "value_total_loan": float(r["value_total_loan"] or 0),
             "value_quota_fixed": float(r["value_quota_fixed"] or 0),
             "created_by_name": None if hide_creator_for and r["created_by"] == hide_creator_for else r["created_by_name"]} for r in rows]


def linked_payment_ids(route_id: UUID, day: date, collector_id: Optional[UUID]):
    """Subconsulta con los pagos que entran al cierre (para el UPDATE que los enlaza)."""
    return _payments_from(select(PaymentModel.id)).where(*payment_conditions(route_id, day, collector_id))


def linked_expense_ids(route_id: UUID, day: date, collector_id: Optional[UUID]):
    return select(ExpenseModel.id).where(*expense_conditions(route_id, day, collector_id))
