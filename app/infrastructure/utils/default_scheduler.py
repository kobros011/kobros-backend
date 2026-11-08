"""Tarea diaria (sin worker): marca como mora las cuotas con fecha de pago vencida.

Corre al arrancar (recupera días en que el servidor estuvo apagado) y luego todos los días a las 00:05 hora Bogotá.
Es idempotente y usa un advisory lock de Postgres para que dos instancias no la ejecuten a la vez.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta

from sqlalchemy import text

from app.core.clock import BOGOTA_TZ, today_bogota
from app.infrastructure.dababase.db import async_session
from app.infrastructure.repositories.default_job_repository import mark_overdue_payments

log = logging.getLogger("kobros.mora_job")
LOCK_KEY = 704_201_001
RUN_AT = (0, 5)  # hora, minuto en Bogotá


def enabled() -> bool:
    return os.getenv("MORA_JOB_ENABLED", "true").lower() not in ("0", "false", "no")


async def run_once(dry_run: bool = False) -> tuple[int, int] | None:
    """Ejecuta el cierre de mora. Devuelve (cuotas, créditos) o None si otra instancia tiene el lock."""
    async with async_session() as db:
        got = (await db.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": LOCK_KEY})).scalar()
        if not got:
            return None
        result = await mark_overdue_payments(db, today_bogota())
        if dry_run:
            await db.rollback()
        else:
            await db.commit()
        return result


def seconds_until_next_run(now: datetime | None = None) -> float:
    now = (now or datetime.now(BOGOTA_TZ)).astimezone(BOGOTA_TZ)
    target = now.replace(hour=RUN_AT[0], minute=RUN_AT[1], second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def loop() -> None:
    while True:
        try:
            result = await run_once()
            log.info("mora_job: %s", "omitido (lock de otra instancia)" if result is None else f"{result[0]} cuotas en mora, {result[1]} créditos")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("mora_job falló; se reintenta en el próximo ciclo")
        await asyncio.sleep(seconds_until_next_run())
