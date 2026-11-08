from datetime import date, datetime

import pytz

BOGOTA_TZ = pytz.timezone("America/Bogota")


def today_bogota(now: datetime | None = None) -> date:
    """Fecha de hoy en Colombia.

    Postgres corre en UTC: `current_date` cambia de día a las 19:00 hora Colombia, así que todo
    cálculo que dependa de "hoy" (mora, cobro diario, períodos) debe recibirla desde aquí como
    parámetro y nunca usar `current_date` en SQL. `now` permite fijar el instante en pruebas.
    """
    instant = now or datetime.now(pytz.utc)
    if instant.tzinfo is None:
        instant = pytz.utc.localize(instant)
    return instant.astimezone(BOGOTA_TZ).date()
