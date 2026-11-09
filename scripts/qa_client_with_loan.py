#!/usr/bin/env python3
"""
QA de crear un cliente junto con su primer crédito (POST /clients/ con `loan`). No borra nada (datos "QD CL").

Comprueba: éxito en una y en varias rutas (con prioridades), cobro inicial, atomicidad (fallo al insertar cuotas ⇒ no queda ni
cliente ni ruta asignada ni número de crédito consumido), validaciones (ruta del crédito fuera de las rutas, cobro antes de la
primera cuota, duplicado), permisos (cobrador sin la ruta, otra marca) y que sin `loan` todo sigue igual.

Uso (contenedor api):  python scripts/qa_client_with_loan.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

import app.main  # noqa: E402,F401
from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.client_model import ClientModel  # noqa: E402
from app.infrastructure.models.client_route_model import ClientRouteModel  # noqa: E402
from app.infrastructure.models.loan_model import LoanModel  # noqa: E402
from app.infrastructure.models.route_model import RouteModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from app.infrastructure.repositories.payment_repository import PaymentRepository  # noqa: E402
from scripts.qa_liquidations import STAMP, new_route  # noqa: E402
from scripts.qa_reports import RESULTS, TOL, Api, check  # noqa: E402

COUNTER = {"n": 0}
BRAND: dict = {}


def body(routes: list[dict], loan: dict | None, label: str, doc: str | None = None) -> dict:
    COUNTER["n"] += 1
    tag = f"{STAMP}{COUNTER['n']:02d}"
    out = {
        "full_name": f"QD CL {label} {tag}", "id_document": doc or f"QD-CL{tag}", "current_address": "Calle QA", "current_phone": "3000000000",
        "current_mobile": "3000000000", "neighborhood": "QA", "linking_date": datetime.now().isoformat(), "routes": routes,
        "brand_id": BRAND["id"],
    }
    if loan is not None:
        out["loan"] = loan
    return out


def loan_in(route_id, *, first=None, value_payment=None, **extra) -> dict:
    first = first or today_bogota()
    data = {"route_id": str(route_id), "value_capital": 300000, "value_quota_fixed": 100000, "agreed_quotas": 4, "payment_method": "semanal",
            "date_first_quota": first.isoformat()}
    if value_payment is not None:
        data["value_payment"] = value_payment
    data.update(extra)
    return data


async def counts(route_id):
    async with async_session() as db:
        loans = (await db.execute(select(func.count()).select_from(LoanModel))).scalar_one()
        clients = (await db.execute(select(func.count()).select_from(ClientModel))).scalar_one()
        links = (await db.execute(select(func.count()).select_from(ClientRouteModel))).scalar_one()
        number = (await db.execute(select(RouteModel.loans_number).where(RouteModel.id == route_id))).scalar_one()
    return loans, clients, links, number


async def main() -> int:
    api = Api()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
    BRAND["id"] = str(norte.id)
    sup, carlos = users["super_norte"], users["qd_carlos"]
    outsider = next((u for u in users.values() if u.brand_id and u.brand_id != norte.id and u.type_user.value in ("02", "03")), None)

    route_a = await new_route([carlos.id], norte.id, "CL-A")
    route_b = await new_route([carlos.id], norte.id, "CL-B")
    a, b = str(route_a.id), str(route_b.id)

    print("== Éxito en una ruta ==")
    r = await api.call(sup, "POST", "/clients/", json=body([{"route_id": a}], loan_in(a, value_payment=100000), "uno"))
    check(r.status_code == 201, "cliente + crédito → 201", r.text[:200])
    client = r.json()
    check(client.get("loan_id") and client.get("loan_number") == 1, "la respuesta trae el id y el número del crédito (#1 en una ruta nueva)", str({k: client.get(k) for k in ("loan_id", "loan_number")}))
    hist = (await api.call(sup, "GET", "/payments/history", params={"loan_id": client["loan_id"], "page_size": 100})).json()
    items = sorted(hist["items"], key=lambda x: x["quota_number"])
    check(len(items) == 4 and abs(items[0]["applied"] - 100000) <= TOL, "se crearon las 4 cuotas y el cobro inicial pagó la primera")
    check(client["routes"][0]["order"] == 1, "el cliente quedó en la ruta con su prioridad")

    print("== Varias rutas: el crédito va a la elegida ==")
    other_client = await api.call(sup, "POST", "/clients/", json=body([{"route_id": a}], None, "previo"))
    r = await api.call(sup, "POST", "/clients/", json=body([{"route_id": a, "order": 1}, {"route_id": b}], loan_in(b), "dos"))
    check(r.status_code == 201, "dos rutas con crédito en la segunda → 201", r.text[:200])
    two = r.json()
    rows_a = (await api.call(sup, "GET", "/clientroute/", params={"route_id": a})).json()
    check([x["order"] for x in rows_a] == list(range(1, len(rows_a) + 1)) and next(x for x in rows_a if x["client_id"] == two["id"])["order"] == 1,
          "la prioridad pedida en la ruta A se aplicó y la ruta sigue 1..n")
    async with async_session() as db:
        loan_route = (await db.execute(
            select(RouteModel.id).join(ClientRouteModel, ClientRouteModel.route_id == RouteModel.id).join(LoanModel, LoanModel.clientroute_id == ClientRouteModel.id)
            .where(LoanModel.id == two["loan_id"]))).scalar_one()
    check(str(loan_route) == b, "el crédito quedó en la ruta B, la elegida")

    print("== Sin crédito: todo como antes ==")
    r = await api.call(sup, "POST", "/clients/", json=body([{"route_id": a}], None, "sin"))
    check(r.status_code == 201 and r.json().get("loan_id") is None, "sin `loan` se crea solo el cliente")

    print("== Validaciones ==")
    r = await api.call(sup, "POST", "/clients/", json=body([{"route_id": a}], loan_in(b), "fuera"))
    check(r.status_code == 422, "ruta del crédito fuera de las rutas del cliente → 422", str(r.status_code))
    before = await counts(route_a.id)
    r = await api.call(sup, "POST", "/clients/", json=body([{"route_id": a}], loan_in(a, first=today_bogota() + timedelta(days=5), value_payment=1000), "futuro"))
    check(r.status_code == 400 and await counts(route_a.id) == before, "cobro inicial con la primera cuota en el futuro → 400 y no queda nada creado")
    r = await api.call(sup, "POST", "/clients/", json=body([{"route_id": a}], loan_in(a, value_capital=0), "cero"))
    check(r.status_code == 422, "capital 0 → 422", str(r.status_code))
    r = await api.call(sup, "POST", "/clients/", json=body([{"route_id": a}], loan_in(a, payment_method="dia_fijo"), "fijo"))
    check(r.status_code == 422, "fecha fija sin día → 422", str(r.status_code))

    print("== Atomicidad ==")
    before = await counts(route_a.id)

    async def boom(self, rows):
        raise RuntimeError("fallo forzado")

    with patch.object(PaymentRepository, "bulk_create_payments", boom):
        try:
            await api.call(sup, "POST", "/clients/", json=body([{"route_id": a}], loan_in(a), "boom"))
            raised = False
        except RuntimeError:
            raised = True
    check(raised and await counts(route_a.id) == before, "con fallo al insertar cuotas no queda cliente, ni ruta asignada, ni crédito, ni número consumido")

    print("== Duplicado ==")
    dup_doc = f"QD-CLDUP{STAMP}"
    r = await api.call(sup, "POST", "/clients/", json=body([{"route_id": a}], None, "dup1", doc=dup_doc))
    assert r.status_code == 201, r.text
    before = await counts(route_a.id)
    r = await api.call(sup, "POST", "/clients/", json=body([{"route_id": a}], loan_in(a), "dup2", doc=dup_doc))
    check(r.status_code == 409 and await counts(route_a.id) == before, "documento repetido con crédito → 409 y no se crea el crédito", str(r.status_code))

    print("== Permisos ==")
    r = await api.call(carlos, "POST", "/clients/", json=body([{"route_id": a, "order": 1}], loan_in(a), "cobrador"))
    check(r.status_code == 201 and r.json().get("loan_number"), "el cobrador crea cliente + crédito en su ruta asignada", r.text[:150])
    other_route = await new_route([sup.id], norte.id, "CL-X")
    r = await api.call(carlos, "POST", "/clients/", json=body([{"route_id": str(other_route.id)}], loan_in(other_route.id), "ajena"))
    check(r.status_code in (403, 404), "el cobrador no puede usar una ruta que no tiene", str(r.status_code))
    if outsider:
        r = await api.call(outsider, "POST", "/clients/", json=body([{"route_id": a}], loan_in(a), "marca"))
        check(r.status_code in (403, 404), "otra marca no puede crear cliente ni crédito en la ruta", str(r.status_code))

    failed = [name for ok_, name in RESULTS if not ok_]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN {len(failed)}" if failed else ""))
    for name in failed:
        print("  ✗", name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
