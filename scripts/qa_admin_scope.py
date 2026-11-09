#!/usr/bin/env python3
"""
QA del alcance por rutas del administrador (03): solo ve lo de las rutas donde está asignado, como socio y cobrador;
dev y super siguen viendo toda su marca. Crea sus propios usuarios, rutas y créditos ("QD AS"); no borra nada.

Comprueba (admin asignado solo a la ruta A, con créditos en A y en B): listados de créditos, clientes, rutas, liquidaciones y
reportes; lecturas por id de lo que es de la ruta B (404/403); filtros que piden la ruta B; un admin sin rutas no ve nada; el admin
que crea una ruta queda asignado; y que el super sigue viendo todo.

Uso (contenedor api):  python scripts/qa_admin_scope.py
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
from app.core.auth import get_password_hash  # noqa: E402
from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.models import UserType  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_liquidations import STAMP, new_loan, new_route  # noqa: E402
from scripts.qa_reports import RESULTS, Api, check  # noqa: E402


async def new_user(kind: UserType, brand_id, label: str) -> UserModel:
    async with async_session() as db:
        user = UserModel(id=uuid4(), username=f"qd_as_{STAMP}_{label}", hashed_password=get_password_hash("x"), full_name=f"QD AS {label}",
                         type_user=kind, brand_id=brand_id, active=True)
        db.add(user)
        await db.commit()
        return user


def items(body):
    return body["items"] if isinstance(body, dict) else body


async def main() -> int:
    api = Api()
    async with async_session() as db:
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        sup = (await db.execute(select(UserModel).where(UserModel.username == "super_norte"))).scalars().first()

    admin = await new_user(UserType.admin, norte.id, "admin")
    lonely = await new_user(UserType.admin, norte.id, "sinrutas")
    route_a = await new_route([admin.id], norte.id, "AS-A")
    route_b = await new_route([], norte.id, "AS-B")
    a, b = str(route_a.id), str(route_b.id)
    loan_a = await new_loan(api, sup, route_a, first_offset=0, value_payment=100000)
    loan_b = await new_loan(api, sup, route_b, first_offset=0, value_payment=100000)

    def client_ids(rows):
        return {x["id"] for x in rows}

    print("== Créditos ==")
    r = await api.call(admin, "GET", "/loans/", params={"page": 1, "page_size": 100})
    loans = {x["id"] for x in items(r.json())}
    check(r.status_code == 200 and loan_a["id"] in loans and loan_b["id"] not in loans, "el listado trae solo los créditos de su ruta", f"{r.status_code} {len(loans)}")
    r = await api.call(admin, "GET", f"/loans/{loan_b['id']}")
    check(r.status_code == 404, "el crédito de otra ruta por id → 404", str(r.status_code))
    r = await api.call(admin, "GET", f"/loans/{loan_a['id']}")
    check(r.status_code == 200, "el crédito de su ruta sí se abre", str(r.status_code))
    r = await api.call(admin, "GET", "/payments/full", params={"route_id": b})
    check(r.status_code in (403, 404), "pagos de otra ruta (filtro por ruta) → denegado", str(r.status_code))
    r = await api.call(admin, "GET", "/payments/", params={"loan_id": loan_b["id"]})
    check(r.status_code == 404, "pagos de un crédito de otra ruta → 404", str(r.status_code))

    print("== Clientes y rutas ==")
    clients_a = {c["id"] for c in (await api.call(sup, "GET", "/clients/", params={"route_id": a})).json()}
    clients_b = {c["id"] for c in (await api.call(sup, "GET", "/clients/", params={"route_id": b})).json()}
    r = await api.call(admin, "GET", "/clients/")
    seen = client_ids(items(r.json()))
    check(r.status_code == 200 and clients_a <= seen and not (clients_b & seen), "el listado de clientes trae solo los de su ruta", f"{len(seen)}")
    r = await api.call(admin, "GET", "/clients/", params={"route_id": b})
    check(r.status_code == 200 and not (clients_b & client_ids(items(r.json()))), "pedir clientes de la ruta B no devuelve nada de B")
    r = await api.call(admin, "GET", f"/clients/{next(iter(clients_b))}")
    check(r.status_code == 404, "un cliente de otra ruta por id → 404", str(r.status_code))
    r = await api.call(admin, "GET", "/routes/")
    routes = {x["id"] for x in items(r.json())}
    check(a in routes and b not in routes, "el listado de rutas trae solo la suya")
    r = await api.call(admin, "GET", f"/routes/{b}")
    check(r.status_code == 404, "otra ruta por id → 404", str(r.status_code))
    r = await api.call(admin, "GET", "/clientroute/", params={"route_id": b})
    check(r.status_code == 404, "los clientes ordenados de otra ruta → 404", str(r.status_code))
    r = await api.call(lonely, "GET", "/clients/")
    check(r.status_code == 200 and not any(c["id"] in (clients_a | clients_b) for c in items(r.json())), "un admin sin rutas no ve clientes de la marca")
    r = await api.call(lonely, "GET", "/loans/", params={"page": 1, "page_size": 100})
    check(r.status_code == 200 and not ({loan_a["id"], loan_b["id"]} & {x["id"] for x in items(r.json())}), "un admin sin rutas no ve créditos")

    # Un cliente que está en la ruta A (del admin) y en la B (ajena): el admin solo ve la A.
    shared = (await api.call(sup, "POST", "/clients/", json={
        "full_name": f"QD AS compartido {STAMP}", "id_document": f"QD-AS{STAMP}", "current_address": "Calle QA", "current_phone": "3000000000",
        "current_mobile": "3000000000", "neighborhood": "QA", "linking_date": "2026-11-09T00:00:00", "brand_id": str(norte.id),
        "routes": [{"route_id": a}, {"route_id": b}]})).json()
    r = await api.call(admin, "GET", "/clients/", params={"route_id": a})
    mine = next((c for c in items(r.json()) if c["id"] == shared["id"]), None)
    check(mine is not None and [x["route_id"] for x in mine["routes"]] == [a], "un cliente en dos rutas solo muestra la ruta del admin", str(mine and mine["routes"]))
    r = await api.call(admin, "GET", f"/clients/{shared['id']}")
    check(r.status_code == 200 and [x["route_id"] for x in r.json()["routes"]] == [a], "el detalle del cliente tampoco muestra la otra ruta", r.text[:160])
    r = await api.call(sup, "GET", f"/clients/{shared['id']}")
    check(len(r.json()["routes"]) == 2, "el super ve las dos rutas del cliente")

    print("== Liquidaciones y reportes ==")
    r = await api.call(admin, "GET", "/liquidations/", params={"page": 1, "page_size": 100})
    check(r.status_code == 200 and all(x["route_id"] in (a,) for x in items(r.json())), "liquidaciones: solo de sus rutas", str(r.status_code))
    r = await api.call(admin, "GET", "/liquidations/preview", params={"route_id": b, "day": "2026-11-09"})
    check(r.status_code in (403, 404), "preview de otra ruta → denegado", str(r.status_code))
    r = await api.call(admin, "GET", "/reports/portfolio", params={"page": 1, "page_size": 100})
    check(r.status_code == 200 and all(x.get("route_name") != route_b.name for x in items(r.json())), "reporte de cartera sin la ruta B")
    r = await api.call(admin, "GET", "/reports/portfolio", params={"route_id": b})
    check(r.status_code == 404, "reporte de otra ruta → 404", str(r.status_code))
    r = await api.call(admin, "GET", f"/reports/clients/{next(iter(clients_b))}/history")
    check(r.status_code == 404, "historial de pagos de un cliente ajeno → 404", str(r.status_code))
    r = await api.call(admin, "GET", "/reports/dashboard/filters")
    check(r.status_code == 200 and {x["id"] for x in r.json().get("routes", [])} <= {a}, "el panel solo ofrece sus rutas", r.text[:120])

    print("== Crear rutas y super ==")
    r = await api.call(admin, "POST", "/routes/", json={"name": f"QD AS nueva {STAMP}", "initial_value": 1000, "initial_expense": 0, "opening_date": "2026-11-09T00:00:00",
                                                       "brand_id": str(norte.id), "allowed_users_ids": []})
    created = r.json() if r.status_code == 201 else {}
    check(r.status_code == 201 and str(admin.id) in [str(x) for x in created.get("allowed_users_ids", [])], "el admin que crea una ruta queda asignado", r.text[:150])
    r = await api.call(sup, "GET", "/loans/", params={"page": 1, "page_size": 100})
    loans = {x["id"] for x in items(r.json())}
    check({loan_a["id"], loan_b["id"]} <= loans, "el super sigue viendo todas las rutas de su marca")
    r = await api.call(sup, "GET", f"/loans/{loan_b['id']}")
    check(r.status_code == 200, "el super abre el crédito de cualquier ruta", str(r.status_code))

    failed = [name for ok_, name in RESULTS if not ok_]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN {len(failed)}" if failed else ""))
    for name in failed:
        print("  ✗", name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
