#!/usr/bin/env python3
"""
QA de la base sugerida del cierre (GET /liquidations/preview): sin cierres previos es el valor inicial de la ruta menos sus
gastos iniciales (nunca negativa); con un cierre activo es la base de ese último cierre. Crea sus datos ("QD LB"); no borra nada.

Uso (contenedor api):  python scripts/qa_liquidation_base.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

import app.main  # noqa: E402,F401
from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.route_model import RouteModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_liquidations import STAMP, new_loan  # noqa: E402
from scripts.qa_reports import RESULTS, Api, check  # noqa: E402


async def route_with(brand_id, initial: float, expense: float, label: str) -> RouteModel:
    async with async_session() as db:
        route = RouteModel(id=uuid4(), name=f"QD LB {STAMP} {label}", initial_value=initial, initial_expense=expense, currency="COP",
                           opening_date=today_bogota(), brand_id=brand_id, allowed_users_ids=[], loans_number=0)
        db.add(route)
        await db.commit()
        return route


async def main() -> int:
    api = Api()
    async with async_session() as db:
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        sup = (await db.execute(select(UserModel).where(UserModel.username == "super_norte"))).scalars().first()
    day = str(today_bogota())

    print("== Sin cierres previos ==")
    route = await route_with(norte.id, 1_000_000, 150_000, "A")
    r = await api.call(sup, "GET", "/liquidations/preview", params={"route_id": str(route.id), "day": day})
    body = r.json()
    check(r.status_code == 200 and body["suggested_base"] == 850_000 and body["suggested_base_source"] == "route_initial",
          "la base sugerida es el valor inicial menos los gastos iniciales", f"{r.status_code} {body.get('suggested_base')} {body.get('suggested_base_source')}")
    route_neg = await route_with(norte.id, 100_000, 300_000, "B")
    r = await api.call(sup, "GET", "/liquidations/preview", params={"route_id": str(route_neg.id), "day": day})
    check(r.json()["suggested_base"] == 0, "nunca sugiere una base negativa")

    print("== Con un cierre previo ==")
    r = await api.call(sup, "POST", "/liquidations/", json={"route_id": str(route.id), "date": day, "value_base_delivered": 400_000, "cash_delivered": 400_000})
    check(r.status_code in (200, 201), "se crea un cierre con base 400.000", f"{r.status_code} {r.text[:120]}")
    r = await api.call(sup, "GET", "/liquidations/preview", params={"route_id": str(route.id), "day": day})
    body = r.json()
    check(body["suggested_base"] == 400_000 and body["suggested_base_source"] == "last_closure", "con un cierre previo sugiere la base de ese cierre", str((body["suggested_base"], body["suggested_base_source"])))

    print("== Efectivo disponible para un crédito nuevo ==")
    fresh = await route_with(norte.id, 1_000_000, 150_000, "C")
    r = await api.call(sup, "GET", "/loans/available-cash", params={"route_id": str(fresh.id)})
    body = r.json()
    check(r.status_code == 200 and body["available"] == 850_000 and body["base"] == 850_000, "ruta nueva: disponible = base (valor inicial menos gastos iniciales)", r.text[:160])
    await new_loan(api, sup, fresh, first_offset=0, value_payment=100_000, capital=400_000)
    r = await api.call(sup, "GET", "/loans/available-cash", params={"route_id": str(fresh.id)})
    body = r.json()
    check(body["new_loans"] == 400_000 and body["collected"] == 100_000 and body["available"] == 550_000,
          "base + cuotas cobradas − créditos entregados = 850.000 + 100.000 − 400.000", str(body))
    await new_loan(api, sup, fresh, first_offset=0, capital=900_000)
    r = await api.call(sup, "GET", "/loans/available-cash", params={"route_id": str(fresh.id)})
    check(r.json()["available"] == 0, "si ya se entregó más de lo que había, el disponible es 0 (nunca negativo)", r.text[:160])
    r = await api.call(sup, "GET", "/loans/available-cash", params={"route_id": str(uuid4())})
    check(r.status_code == 404, "ruta inexistente → 404", str(r.status_code))

    failed = [name for ok_, name in RESULTS if not ok_]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN {len(failed)}" if failed else ""))
    for name in failed:
        print("  ✗", name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
