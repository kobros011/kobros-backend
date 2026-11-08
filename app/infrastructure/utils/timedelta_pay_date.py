from datetime import date, datetime, timedelta
from typing import List, Optional
from .Emun import PaymentMethod
import calendar

def add_months(dt: datetime, months: int) -> datetime:
    """
    Suma `months` meses reales a la fecha `dt`.
    Si el día no existe en el mes destino, se ajusta al último día de ese mes.
    """
    # calcula año y mes de destino
    total_months = dt.year * 12 + (dt.month - 1) + months
    new_year = total_months // 12
    new_month = total_months % 12 + 1

    # día máximo en el mes de destino
    last_day = calendar.monthrange(new_year, new_month)[1]
    new_day = min(dt.day, last_day)

    return dt.replace(year=new_year, month=new_month, day=new_day)

def timedelta_pay_date(current: int, payment_method: str):
    if payment_method == PaymentMethod.DIARY.value:
        return timedelta(days=current)
    if payment_method == PaymentMethod.WEEKLY.value:
        return timedelta(weeks=current)
    if payment_method == PaymentMethod.FORTNIGHTLY.value:
        return timedelta(weeks=current*2)
    
    return timedelta(days=current)


def build_payment_schedule(first_date: date, payment_method: str, quotas: int, fixed_day: Optional[int] = None) -> List[date]:
    """Fecha de vencimiento de cada cuota (en orden). `mensual`/`dia_fijo` usan meses reales; el resto, saltos fijos."""
    if payment_method == PaymentMethod.MONTHLY.value:
        return [add_months(first_date, i) for i in range(quotas)]
    if payment_method == PaymentMethod.FIXED_DATE.value:
        dates = []
        for i in range(quotas):
            base = add_months(first_date, i)
            last_day = calendar.monthrange(base.year, base.month)[1]
            dates.append(base.replace(day=min(fixed_day or base.day, last_day)))
        return dates
    return [first_date + timedelta_pay_date(i, payment_method) for i in range(quotas)]
