#!/usr/bin/env python3
"""
Dataset pequeño y legible para las capturas del manual de usuario (marca NORTE01, base local).

1) BORRA los datos operativos de prueba de NORTE01 (pagos, créditos, gastos, liquidaciones, movimientos de caja, clientes y rutas).
   Conserva la marca, sus ajustes (monedas), los usuarios y los conceptos de gasto. Solo base local; sin respaldo por decisión del usuario.
2) Crea 3 rutas (2 en COP y 1 en USD), 7 clientes con créditos en distintos estados, 2 gastos y 2 cierres de caja.

Uso (contenedor api):  python scripts/seed_manual_demo.py          (muestra qué borraría y pide --yes para ejecutar)
                       python scripts/seed_manual_demo.py --yes
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text  # noqa: E402

import app.main  # noqa: E402,F401
from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.expense_model import ExpenseConceptModel  # noqa: E402
from app.infrastructure.models.route_model import RouteModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_reports import Api  # noqa: E402

# Orden de borrado: hijos primero. Todo filtrado por la marca.
DELETES = [
    ("payments", "DELETE FROM payments WHERE loan_id IN (SELECT l.id FROM loans l JOIN clientsroutes cr ON cr.id=l.clientroute_id JOIN routes r ON r.id=cr.route_id WHERE r.brand_id=:b)"),
    ("loans", "DELETE FROM loans WHERE clientroute_id IN (SELECT cr.id FROM clientsroutes cr JOIN routes r ON r.id=cr.route_id WHERE r.brand_id=:b)"),
    ("expenses", "DELETE FROM expenses WHERE route_id IN (SELECT id FROM routes WHERE brand_id=:b)"),
    ("liquidations", "DELETE FROM liquidations WHERE route_id IN (SELECT id FROM routes WHERE brand_id=:b)"),
    ("route_movements", "DELETE FROM route_movements WHERE route_id IN (SELECT id FROM routes WHERE brand_id=:b)"),
    ("clientsroutes", "DELETE FROM clientsroutes WHERE route_id IN (SELECT id FROM routes WHERE brand_id=:b) OR cliente_id IN (SELECT id FROM clients WHERE brand_id=:b)"),
    ("client_references", "DELETE FROM client_references WHERE client_id IN (SELECT id FROM clients WHERE brand_id=:b)"),
    ("clients", "DELETE FROM clients WHERE brand_id=:b"),
    ("routes", "DELETE FROM routes WHERE brand_id=:b"),
]
COUNTS = {
    "payments": "SELECT count(*) FROM payments p JOIN loans l ON l.id=p.loan_id JOIN clientsroutes cr ON cr.id=l.clientroute_id JOIN routes r ON r.id=cr.route_id WHERE r.brand_id=:b",
    "loans": "SELECT count(*) FROM loans l JOIN clientsroutes cr ON cr.id=l.clientroute_id JOIN routes r ON r.id=cr.route_id WHERE r.brand_id=:b",
    "expenses": "SELECT count(*) FROM expenses WHERE route_id IN (SELECT id FROM routes WHERE brand_id=:b)",
    "liquidations": "SELECT count(*) FROM liquidations WHERE route_id IN (SELECT id FROM routes WHERE brand_id=:b)",
    "clients": "SELECT count(*) FROM clients WHERE brand_id=:b",
    "routes": "SELECT count(*) FROM routes WHERE brand_id=:b",
}


async def new_route(name, brand, currency, allowed, initial):
    async with async_session() as db:
        route = RouteModel(id=uuid4(), name=name, initial_value=initial, initial_expense=0, currency=currency, opening_date=today_bogota(),
                           brand_id=brand.id, allowed_users_ids=allowed, loans_number=0)
        db.add(route)
        await db.commit()
        return route


async def new_loan(api, user, route, full_name, doc, mobile, address, *, method, capital, quota, quotas, first_offset, paid_today=None):
    r = await api.call(user, "POST", "/clients/", json={
        "full_name": full_name, "id_document": doc, "current_address": address, "current_phone": mobile, "current_mobile": mobile,
        "neighborhood": "Centro", "linking_date": datetime.now().isoformat(), "routes_ids": [str(route.id)], "brand_id": str(user.brand_id)})
    assert r.status_code == 201, r.text
    client = r.json()
    crs = (await api.call(user, "GET", "/clientroute/", params={"route_id": str(route.id)})).json()
    cr = next(c for c in crs if c["client_id"] == client["id"])
    body = {"value_quota_fixed": quota, "agreed_quotas": quotas, "date_first_quota": (today_bogota() + timedelta(days=first_offset)).isoformat(),
            "payment_method": method, "value_capital": capital, "current_address": address, "current_mobile": mobile,
            "clientroute_id": cr["id"], "client_id": client["id"]}
    if paid_today is not None:
        body["value_payment"] = paid_today
    r = await api.call(user, "POST", "/loans/", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def pay(api, user, loan_id, number, value):
    r = await api.call(user, "GET", "/payments/history", params={"loan_id": loan_id, "page_size": 100})
    q = next(i for i in r.json()["items"] if i["quota_number"] == number)
    r = await api.call(user, "PUT", f"/payments/{q['id']}/pay", params={"value": value})
    assert r.status_code == 200, r.text


async def main(confirm: bool) -> int:
    async with async_session() as db:
        brand = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        users = {u.username: u for u in (await db.execute(select(UserModel).where(UserModel.brand_id == brand.id))).scalars().all()}
        concept = (await db.execute(select(ExpenseConceptModel).where(ExpenseConceptModel.concept == "Combustible", ExpenseConceptModel.brand_id == brand.id))).scalars().first()
        print(f"Marca {brand.code}: se borrarían ->", {k: (await db.execute(text(q), {"b": brand.id})).scalar() for k, q in COUNTS.items()})
    if not confirm:
        print("Nada borrado. Corre con --yes para limpiar y sembrar.")
        return 0

    async with async_session() as db:
        for name, sql in DELETES:
            res = await db.execute(text(sql), {"b": brand.id})
            print(f"  borrado {name}: {res.rowcount}")
        await db.commit()

    api = Api()
    sup, carlos, julian, laura = users["super_norte"], users["qd_carlos"], users["qd_julian"], users["qd_laura"]
    centro = await new_route("Ruta Centro", brand, "COP", [carlos.id, sup.id], 2_000_000)
    norte = await new_route("Ruta Norte", brand, "COP", [julian.id, sup.id], 1_500_000)
    dolares = await new_route("Ruta Dólares", brand, "USD", [laura.id, sup.id], 1_000)

    # Ruta Centro (COP): un crédito en mora, uno al día que paga hoy y uno que aún no vence
    marta = await new_loan(api, sup, centro, "Marta Lucía Rojas", "52100200", "3105550101", "Cra 7 # 12-30", method="diaria", capital=500000, quota=25000, quotas=24, first_offset=-3)
    jorge = await new_loan(api, sup, centro, "Jorge Ramírez", "80200300", "3125550102", "Calle 45 # 8-15", method="semanal", capital=800000, quota=100000, quotas=10, first_offset=0, paid_today=100000)
    await new_loan(api, sup, centro, "Luz Dary Gómez", "43300400", "3135550103", "Av. 30 # 20-11", method="quincenal", capital=1200000, quota=250000, quotas=6, first_offset=5)
    await pay(api, carlos, marta["id"], 1, 25000)
    await pay(api, carlos, marta["id"], 2, 10000)          # abono parcial → queda en mora

    # Ruta Norte (COP)
    cm = await new_loan(api, sup, norte, "Carlos Mendoza", "71400500", "3145550104", "Cll 80 # 50-22", method="diaria", capital=300000, quota=15000, quotas=24, first_offset=0)
    await new_loan(api, sup, norte, "Sandra Peña", "63500600", "3155550105", "Cra 15 # 33-40", method="semanal", capital=600000, quota=80000, quotas=9, first_offset=-7)
    await pay(api, julian, cm["id"], 1, 15000)

    # Ruta Dólares (USD, con centavos)
    av = await new_loan(api, sup, dolares, "Andrés Vélez", "98700800", "3165550106", "Cll 10 # 4-50", method="diaria", capital=100, quota=20.5, quotas=6, first_offset=0)
    po = await new_loan(api, sup, dolares, "Paola Ortiz", "37800900", "3175550107", "Cra 3 # 22-18", method="semanal", capital=300, quota=40, quotas=9, first_offset=-7)
    await pay(api, laura, av["id"], 1, 20.5)
    await pay(api, laura, po["id"], 1, 25)

    # Caja de la ruta Centro: aporte de capital para que el saldo no quede negativo
    r = await api.call(sup, "POST", "/route-movements/", json={"route_id": str(centro.id), "type": "INGRESO", "value": 1000000, "concept": "Aporte de capital"})
    assert r.status_code == 201, r.text

    # Gastos y cierres
    today = today_bogota().isoformat()
    for user, route, value, name in ((carlos, centro, 15000, "Gasolina moto"), (laura, dolares, 4.75, "Transporte")):
        r = await api.call(user, "POST", "/expenses/", json={"date": today, "value": value, "name": name, "expensesconcept_id": str(concept.id), "route_id": str(route.id)})
        assert r.status_code == 201, r.text

    # Cierre confirmado (Ruta Norte): base 0, esperado = recaudo (15.000) − créditos nuevos de hoy (300.000 + 600.000)
    prev = (await api.call(sup, "GET", "/liquidations/preview", params={"route_id": str(norte.id), "date": today, "collector_id": str(julian.id)})).json()
    r = await api.call(sup, "POST", "/liquidations/", json={"route_id": str(norte.id), "date": today, "value_base_delivered": 0, "cash_delivered": prev["expected_cash"],
                                                           "collector_id": str(julian.id), "note": "Cuadre exacto"})
    assert r.status_code == 201, r.text
    r2 = await api.call(sup, "POST", f"/liquidations/{r.json()['id']}/confirm")
    assert r2.status_code == 200, r2.text
    # Cierre pendiente con faltante (Ruta Dólares)
    prev = (await api.call(sup, "GET", "/liquidations/preview", params={"route_id": str(dolares.id), "date": today, "collector_id": str(laura.id)})).json()
    r = await api.call(sup, "POST", "/liquidations/", json={"route_id": str(dolares.id), "date": today, "value_base_delivered": 0, "cash_delivered": round(prev["expected_cash"] - 0.5, 2),
                                                           "collector_id": str(laura.id), "note": "Faltan 50 centavos"})
    assert r.status_code == 201, r.text
    print("OK: dataset demo creado (3 rutas, 7 clientes y créditos, 2 gastos, 2 cierres)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--yes" in sys.argv)))
