#!/usr/bin/env python3
"""QA del job diario de mora: cuotas vencidas sin cobrar pasan a 'mora' y suman su faltante a total_default.

Uso (contenedor api):  python scripts/qa_mora_job.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.loan_model import LoanModel  # noqa: E402
from app.infrastructure.models.payment_model import PaymentModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from app.infrastructure.utils.default_scheduler import run_once, seconds_until_next_run  # noqa: E402
from scripts.qa_liquidations import new_loan, new_route  # noqa: E402
from scripts.qa_reports import RESULTS, Api, check  # noqa: E402


async def state(loan_id):
    async with async_session() as db:
        loan = await db.get(LoanModel, loan_id)
        pays = (await db.execute(select(PaymentModel).where(PaymentModel.loan_id == loan_id).order_by(PaymentModel.quota_number))).scalars().all()
        return float(loan.total_default or 0), {p.quota_number: p for p in pays}


async def main() -> int:
    api = Api()
    today = today_bogota()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
    sup, carlos = users["super_norte"], users["qd_carlos"]
    route = await new_route([carlos.id], norte.id, "MORA")
    loan = await new_loan(api, sup, route, first_offset=0)
    inactive = await new_loan(api, sup, route, first_offset=0)
    lid, iid = loan["id"], inactive["id"]

    async with async_session() as db:
        pays = {p.quota_number: p for p in (await db.execute(select(PaymentModel).where(PaymentModel.loan_id == lid))).scalars().all()}
        d = lambda n: today - timedelta(days=n)
        # q1 pagada vencida · q2 parcial (ya en mora) · q3,q4 vencidas sin cobrar · q5 vence hoy · q6 futura
        for n, (offset, status, applied) in {1: (5, "pagado", 100000), 2: (4, "mora", 40000), 3: (3, "pendiente", None),
                                             4: (2, "pendiente", None), 5: (0, "pendiente", None), 6: (-3, "pendiente", None)}.items():
            p = pays[n]
            p.pay_date, p.status, p.applied = d(offset), status, applied
        (await db.get(LoanModel, lid)).total_default = 60000  # faltante ya contado de q2
        for p in (await db.execute(select(PaymentModel).where(PaymentModel.loan_id == iid))).scalars().all():
            p.pay_date = d(3)
        (await db.get(LoanModel, iid)).active = False
        await db.commit()

    print("== Marcado de mora ==")
    dry = await run_once(dry_run=True)
    td, ps = await state(lid)
    check(dry is not None and dry[0] >= 2 and ps[3].status == "pendiente" and td == 60000, "dry-run no cambia nada")
    res = await run_once()
    td, ps = await state(lid)
    check(res is not None and res[0] >= 2, f"el job marcó cuotas ({res})")
    check(ps[3].status == "mora" and ps[4].status == "mora", "cuotas vencidas sin cobrar → mora")
    check(ps[1].status == "pagado", "cuota pagada intacta")
    check(ps[5].status == "pendiente" and ps[6].status == "pendiente", "cuota que vence hoy y futura siguen pendientes")
    check(abs(td - 260000) < 0.01, f"total_default suma los faltantes (60.000 + 2×100.000 = 260.000) → {td}")
    _, ips = await state(iid)
    check(all(p.status == "pendiente" for p in ips.values()), "crédito inactivo no se toca")

    print("== Idempotencia y cobro posterior ==")
    await run_once()
    td2, _ = await state(lid)
    check(abs(td2 - 260000) < 0.01, "segunda ejecución no vuelve a sumar")
    r = await api.call(sup, "PUT", f"/payments/{ps[3].id}/pay", params={"value": 100000})
    check(r.status_code == 200, "cobrar una cuota en mora (200)", r.text[:120])
    td3, ps3 = await state(lid)
    check(ps3[3].status == "pagado" and abs(td3 - 160000) < 0.01, f"el cobro resta su faltante: total_default = 160.000 → {td3}")
    r = await api.call(sup, "PUT", f"/payments/{ps[4].id}/pay", params={"value": 30000})
    td4, _ = await state(lid)
    check(abs(td4 - 130000) < 0.01, f"cobro parcial de 30.000 deja faltante 70.000: total_default = 60.000 + 70.000 = 130.000 → {td4}")

    print("== Programación ==")
    from datetime import datetime
    from app.core.clock import BOGOTA_TZ
    s = seconds_until_next_run(BOGOTA_TZ.localize(datetime(2026, 1, 1, 23, 0)))
    check(abs(s - 65 * 60) < 1, "desde las 23:00 faltan 65 min para las 00:05")
    s = seconds_until_next_run(BOGOTA_TZ.localize(datetime(2026, 1, 1, 0, 6)))
    check(abs(s - (23 * 3600 + 59 * 60)) < 1, "a las 00:06 la próxima corrida es mañana")

    failed = [n for ok, n in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
