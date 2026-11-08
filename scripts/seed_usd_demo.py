#!/usr/bin/env python3
"""
Datos de prueba en USD para revisar la UI con dos monedas. No borra nada.

Usa la ruta "QA Moneda USD" de la marca NORTE01 (se crea desde Rutas con moneda USD): un crédito con un cobro de la
cuota de hoy, una cuota vencida cobrada y un gasto. Se puede correr varias veces (crea un cliente y crédito nuevos cada vez).

Uso (contenedor api):  python scripts/seed_usd_demo.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

import app.main  # noqa: E402,F401
from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.expense_model import ExpenseConceptModel  # noqa: E402
from app.infrastructure.models.route_model import RouteModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_reports import Api  # noqa: E402

STAMP = datetime.now().strftime("%H%M%S")


async def loan(api, user, route_id, cr_lookup_route, *, first_offset: int, n: int):
    r = await api.call(user, "POST", "/clients/", json={
        "full_name": f"USD Cliente {STAMP}-{n}", "id_document": f"USD-{STAMP}{n}", "current_address": "Calle USD", "current_phone": "3000000000",
        "current_mobile": "3000000000", "neighborhood": "QA", "linking_date": datetime.now().isoformat(),
        "routes_ids": [str(route_id)], "brand_id": str(user.brand_id)})
    assert r.status_code == 201, r.text
    client = r.json()
    crs = (await api.call(user, "GET", "/clientroute/", params={"route_id": str(route_id)})).json()
    cr = next(c for c in crs if c["client_id"] == client["id"])
    first = today_bogota() + timedelta(days=first_offset)
    r = await api.call(user, "POST", "/loans/", json={
        "value_quota_fixed": 20.5, "agreed_quotas": 6, "date_first_quota": first.isoformat(), "payment_method": "diaria", "value_capital": 100,
        "current_address": "Calle USD", "current_mobile": "3000000000", "clientroute_id": cr["id"], "client_id": client["id"]})
    assert r.status_code == 201, r.text
    return r.json()


async def pay(api, user, loan_id, number, value):
    r = await api.call(user, "GET", "/payments/history", params={"loan_id": loan_id, "page_size": 100})
    q = next(i for i in r.json()["items"] if i["quota_number"] == number)
    r = await api.call(user, "PUT", f"/payments/{q['id']}/pay", params={"value": value})
    assert r.status_code == 200, r.text


async def main() -> int:
    api = Api()
    async with async_session() as db:
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        route = (await db.execute(select(RouteModel).where(RouteModel.brand_id == norte.id, RouteModel.name == "QA Moneda USD"))).scalars().first()
        sup = (await db.execute(select(UserModel).where(UserModel.username == "super_norte"))).scalars().first()
        concept = (await db.execute(select(ExpenseConceptModel).where(ExpenseConceptModel.concept == "Combustible", ExpenseConceptModel.brand_id == norte.id))).scalars().first()
    assert route is not None and route.currency == "USD", "Falta la ruta USD 'QA Moneda USD' (créala en Rutas con moneda USD)"

    a = await loan(api, sup, route.id, route.id, first_offset=0, n=1)     # cuota de hoy
    b = await loan(api, sup, route.id, route.id, first_offset=-3, n=2)    # cuotas vencidas
    await pay(api, sup, a["id"], 1, 20.5)
    await pay(api, sup, b["id"], 1, 12.25)                               # abono parcial de una cuota atrasada
    r = await api.call(sup, "POST", "/expenses/", json={"date": today_bogota().isoformat(), "value": 4.75, "name": "QA gasto USD",
                                                        "expensesconcept_id": str(concept.id), "route_id": str(route.id)})
    assert r.status_code == 201, r.text
    print(f"OK: créditos {a['id']} y {b['id']} en la ruta USD {route.id}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
