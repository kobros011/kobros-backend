from datetime import datetime, timedelta
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