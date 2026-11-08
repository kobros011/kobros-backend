"""Reglas de aplicación de un cobro a una cuota, compartidas por el abono (`pay_payment`) y la creación de crédito.

Una cuota con cobro `value` frente a la cuota fija `quota`:
* faltante  = quota − value  si value < quota  (suma a `loan.total_default`, la cuota queda en mora parcial)
* excedente = value − quota  si value > quota  (suma a `client.beak`, saldo a favor)

Al corregir un abono ya aplicado se resta el efecto anterior y se suma el nuevo, así `beak` y `total_default`
acumulan entre cuotas en vez de pisarse.
"""
from datetime import date
from typing import Any, Optional
from uuid import UUID

from .Emun import PaymentStatus


def apply_payment_to_quota(payment: Any, loan: Any, client: Any, value: float, today: date, collected_by: Optional[UUID]) -> None:
    quota = float(loan.value_quota_fixed or 0)
    value = float(value or 0)
    old_applied = float(payment.applied or 0)
    was_default = payment.status == PaymentStatus.default.value

    old_shortfall = max(quota - old_applied, 0) if was_default else 0.0
    old_excess = max(old_applied - quota, 0)
    new_shortfall = max(quota - value, 0)
    new_excess = max(value - quota, 0)

    loan.total_default = max(float(loan.total_default or 0) - old_shortfall + new_shortfall, 0)
    client.beak = max(float(client.beak or 0) - old_excess + new_excess, 0)

    payment.payment_date = today
    payment.applied = value
    payment.collected_by = collected_by
    payment.status = PaymentStatus.default.value if value < quota else PaymentStatus.paid.value
    loan.canceled_quotas = payment.quota_number
    loan.pending_quotas = (loan.agreed_quotas or 0) - payment.quota_number
