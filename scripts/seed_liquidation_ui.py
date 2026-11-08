#!/usr/bin/env python3
"""
Prepara (sin tocar Clerk) la ruta "QD UI Liquidación" para probar el flujo de liquidaciones desde la interfaz:

  * ruta asignada al cobrador `qd_carlos` y al admin `admin_norte` (mismo flujo que `qa_liquidations_flow.py`);
  * 8 clientes con crédito: 5 con cuota que vence HOY, 2 con cuotas atrasadas y 1 más para abonar a mano.
Es idempotente: si la ruta ya tiene clientes no crea más. No borra nada.

Uso (contenedor api):  python scripts/seed_liquidation_ui.py
Luego, en la UI: el cobrador cobra y registra gastos; el admin cierra la caja en Liquidaciones.
"""
from __future__ import annotations

import asyncio
import logging
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
from app.infrastructure.dababase.db import async_session, engine  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.route_model import RouteModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_reports import Api  # noqa: E402

engine.echo = False
logging.disable(logging.CRITICAL)

ROUTE_NAME = "QD UI Liquidación"
CLIENTS = [("Ana María Torres", 0), ("Bruno Díaz Pérez", 0), ("Carla Gómez Ruiz", 0), ("Diego Herrera Mora", 0), ("Elena Castro Vega", 0),
           ("Fabio Ríos Salas", -4), ("Gloria Peña Lara", -3), ("Hernán Soto Díaz", 0)]


async def main() -> int:
    api = Api()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        brand = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        route = (await db.execute(select(RouteModel).where(RouteModel.name == ROUTE_NAME, RouteModel.brand_id == brand.id))).scalars().first()
        carlos, admin, sup = users["qd_carlos"], users["admin_norte"], users["super_norte"]
        if route is None:
            route = RouteModel(id=uuid4(), name=ROUTE_NAME, initial_value=2_000_000, initial_expense=0, opening_date=today_bogota(),
                               brand_id=brand.id, allowed_users_ids=[carlos.id, admin.id, sup.id], loans_number=0)
            db.add(route)
            await db.commit()
            print(f"Ruta creada: {ROUTE_NAME}")
        else:
            allowed = set(route.allowed_users_ids or [])
            if not {carlos.id, admin.id} <= allowed:
                await db.execute(text("UPDATE routes SET allowed_users_ids = :ids WHERE id = :r"), {"ids": list(allowed | {carlos.id, admin.id, sup.id}), "r": route.id})
                await db.commit()
        existing = (await db.execute(text("SELECT count(*) FROM clientsroutes WHERE route_id = :r"), {"r": route.id})).scalar_one()

    if existing:
        print(f"La ruta ya tiene {existing} clientes: no se crean más.")
        return 0

    today = today_bogota()
    for i, (name, offset) in enumerate(CLIENTS, start=1):
        r = await api.call(sup, "POST", "/clients/", json={
            "full_name": name, "id_document": f"QD-UI{i:02d}", "current_address": f"Calle {i} #10-{i}", "current_phone": "6010000000",
            "current_mobile": f"31000000{i:02d}", "neighborhood": "Centro", "linking_date": datetime.now().isoformat(),
            "routes_ids": [str(route.id)], "brand_id": str(sup.brand_id)})
        client = r.json()
        crs = (await api.call(sup, "GET", "/clientroute/", params={"route_id": str(route.id)})).json()
        cr = next(c for c in crs if c["client_id"] == client["id"])
        first = today + timedelta(days=offset)
        r = await api.call(sup, "POST", "/loans/", json={
            "end_date": (first + timedelta(days=30)).isoformat(), "value_quota_fixed": 100000, "agreed_quotas": 8, "date_first_quota": first.isoformat(),
            "payment_method": "diaria", "value_capital": 600000, "current_address": f"Calle {i} #10-{i}", "current_mobile": f"31000000{i:02d}",
            "clientroute_id": cr["id"], "client_id": client["id"]})
        assert r.status_code == 201, r.text
    print(f"Creados {len(CLIENTS)} clientes con crédito en '{ROUTE_NAME}' (5 con cuota de hoy, 2 atrasados, 1 para abonar).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
