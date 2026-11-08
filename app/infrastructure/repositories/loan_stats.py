"""Fuente única de las cifras por crédito (pagado, saldo, mora).

Cartera, Cartera en mora y el Dashboard de Reportes consumen esta misma subconsulta, así que sus
números coinciden siempre. Definiciones (hoy = fecha Bogotá, ver `app.core.clock`):

* pagado          = Σ coalesce(applied, 0) de los pagos del crédito (el status no importa: un pago
                    parcial queda con status 'mora' y `applied < value`).
* saldo           = value_total_loan − pagado.
* cuota vencida   = pago con pay_date < hoy y value − coalesce(applied, 0) > 0.01.
* overdue_amount  = LEAST(Σ(value − applied) de cuotas vencidas, saldo).
* overdue_since   = MIN(pay_date) de las cuotas vencidas; days_overdue = hoy − overdue_since.
"""
from datetime import date

from sqlalchemy import Date, Integer, func, literal, select
from sqlalchemy.sql import Subquery

from ..models.loan_model import LoanModel
from ..models.payment_model import PaymentModel

CRITICAL_DAYS = 30
UNPAID_TOLERANCE = 0.01


def build_loan_stats(today: date) -> Subquery:
    """Una fila por crédito con paid, balance, overdue_amount, overdue_quotas, overdue_since, days_overdue."""
    unpaid = PaymentModel.value - func.coalesce(PaymentModel.applied, 0)
    is_overdue = (PaymentModel.pay_date < today) & (unpaid > UNPAID_TOLERANCE)

    pay = (
        select(
            PaymentModel.loan_id.label("loan_id"),
            func.coalesce(func.sum(PaymentModel.applied), 0).label("paid"),
            func.coalesce(func.sum(func.greatest(unpaid, 0)).filter(is_overdue), 0).label("overdue_raw"),
            func.count().filter(is_overdue).label("overdue_quotas"),
            func.min(PaymentModel.pay_date).filter(is_overdue).label("overdue_since"),
        )
        .group_by(PaymentModel.loan_id)
        .subquery("pay")
    )

    total = func.coalesce(LoanModel.value_total_loan, 0)
    paid = func.coalesce(pay.c.paid, 0)
    balance = total - paid
    overdue_since = pay.c.overdue_since

    return (
        select(
            LoanModel.id.label("loan_id"),
            total.label("value_total_loan"),
            paid.label("paid"),
            balance.label("balance"),
            func.least(func.coalesce(pay.c.overdue_raw, 0), balance).label("overdue_amount"),
            func.coalesce(pay.c.overdue_quotas, 0).label("overdue_quotas"),
            overdue_since.label("overdue_since"),
            (literal(today, Date) - overdue_since).cast(Integer).label("days_overdue"),
        )
        .select_from(LoanModel)
        .outerjoin(pay, pay.c.loan_id == LoanModel.id)
        .subquery("loan_stats")
    )
