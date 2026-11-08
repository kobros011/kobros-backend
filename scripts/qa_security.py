#!/usr/bin/env python3
"""
QA de seguridad (alcance entre marcas y roles) sobre TODOS los endpoints que reciben un id.

Con datos reales de la marca NORTE01 (ruta, cliente, crédito, pago, gasto, concepto, usuario, cierre) prueba:
  A) un administrador de OTRA marca: ninguna lectura/escritura sobre recursos de NORTE01 debe responder 2xx;
  B) un cobrador NO asignado a la ruta: no debe ver ni tocar recursos de la ruta;
  C) un cobrador asignado: no debe poder ejecutar acciones de administración (rutas, usuarios, marcas, pagos manuales).
Imprime una tabla "endpoint → respuesta" y falla si algo que debía rechazarse devuelve 2xx. No borra nada
(las escrituras exitosas que no deberían ocurrir se detectan y se reportan; las pruebas usan cuerpos inofensivos).

Uso (contenedor api):  python scripts/qa_security.py
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

from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.expense_model import ExpenseConceptModel, ExpenseModel  # noqa: E402
from app.infrastructure.models.liquidation_model import LiquidationModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_liquidations import new_loan, new_route  # noqa: E402
from scripts.qa_reports import RESULTS, Api, check  # noqa: E402


async def main() -> int:
    api = Api()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        concept = (await db.execute(select(ExpenseConceptModel).where(ExpenseConceptModel.brand_id == norte.id))).scalars().first()
        liq = (await db.execute(select(LiquidationModel).order_by(LiquidationModel.created_at.desc()).limit(1))).scalars().first()
    sup, carlos, julian, laura = users["super_norte"], users["qd_carlos"], users["qd_julian"], users["qd_laura"]
    outsider = next((u for u in users.values() if u.brand_id and u.brand_id != norte.id and u.type_user.value in ("02", "03")), None)
    if outsider is None:
        print("No hay un administrador de otra marca para la prueba A")
        return 1

    route = await new_route([carlos.id], norte.id, "SEC")
    loan = await new_loan(api, sup, route, first_offset=0)
    q = (await api.call(sup, "GET", "/payments/history", params={"loan_id": loan["id"]})).json()["items"][0]
    crs = (await api.call(sup, "GET", "/clientroute/", params={"route_id": str(route.id)})).json()
    cr = crs[0]
    client_id = cr["client_id"]
    r = await api.call(sup, "POST", "/expenses/", json={"date": "2026-11-07", "value": 1000, "name": "QA sec", "expensesconcept_id": str(concept.id), "route_id": str(route.id)})
    expense_id = r.json()["id"]
    async with async_session() as db:
        liq_in_route = liq
    print(f"Recursos: ruta={route.id} cliente={client_id} crédito={loan['id']}")

    rid, lid, pid = str(route.id), loan["id"], q["id"]
    cases = [  # (método, ruta, cuerpo/params)
        ("GET", f"/routes/{rid}", None), ("PUT", f"/routes/{rid}", {"id": rid, "name": "hack", "initial_value": 1, "initial_expense": 1, "opening_date": "2026-01-01", "allowed_users_ids": []}),
        ("PUT", f"/routes/{rid}/toggle", None),
        ("GET", f"/clients/{client_id}", None), ("GET", f"/clients/{client_id}/more_info/", None),
        ("PUT", f"/clients/{client_id}", {"id": client_id, "full_name": "hack"}), ("PUT", f"/clients/{client_id}/toggle", None),
        ("GET", f"/clientroute/{cr['id']}", None), ("GET", "/clientroute/", {"params": {"route_id": rid}}),
        ("PUT", f"/clientroute/{cr['id']}", {"id": cr["id"], "order": 1}),
        ("GET", f"/expenses/{expense_id}", None), ("PUT", f"/expenses/{expense_id}/toggle", None), ("DELETE", f"/expenses/{expense_id}", None),
        ("GET", f"/payments/{pid}", None), ("PUT", f"/payments/{pid}/pay", {"params": {"value": 5}}), ("DELETE", f"/payments/{pid}", None),
        ("GET", "/payments/today", {"params": {"route_id": rid}}), ("GET", "/payments/full", {"params": {"route_id": rid}}),
        ("GET", "/payments/history", {"params": {"loan_id": lid}}), ("GET", "/payments/", {"params": {"loan_id": lid}}),
        ("GET", f"/loans/{lid}", None), ("DELETE", f"/loans/{lid}", None), ("GET", "/loans/", {"params": {"route_id": rid}}),
        ("GET", "/reports/dashboard/summary", {"params": {"route_id": rid}}), ("GET", f"/reports/clients/{client_id}/history", None),
        ("GET", "/route-movements/", {"params": {"route_id": rid}}), ("GET", "/route-movements/summary", {"params": {"route_id": rid}}),
        ("GET", f"/users/{laura.id}", None), ("PUT", f"/users/{laura.id}/toggle", None),
        ("GET", f"/brands/{norte.id}", None),
        ("GET", f"/liquidations/{liq_in_route.id}", None),
        ("GET", f"/expensesconcepts/{concept.id}", None), ("PUT", f"/expensesconcepts/{concept.id}/toggle", None),
    ]

    class _Failed:
        status_code = 500

    async def safe_call(user, method, path, **kwargs):
        try:
            return await api.call(user, method, path, **kwargs)
        except Exception:  # un 500 no es una fuga (pero se ve en la tabla como 500)
            return _Failed()

    async def run(user, label, skip: tuple = ()):
        print(f"\n== {label} ==")
        for method, path, extra in cases:
            if any(path.startswith(x) for x in skip):
                continue  # datos de la propia marca: un cobrador de la misma marca sí puede leerlos
            kwargs = {}
            if extra and "params" in extra:
                kwargs["params"] = extra["params"]
            elif extra:
                kwargs["json"] = extra
            res = await safe_call(user, method, path, **kwargs)
            leaked = res.status_code < 300
            if leaked and method == "GET":  # un listado vacío no filtra nada
                try:
                    body = res.json()
                    items = body.get("items") if isinstance(body, dict) else body
                    if isinstance(items, list) and len(items) == 0:
                        leaked = False
                except Exception:
                    pass
            key = f"{method} {path.split('?')[0]}"
            flagged = leaked
            check(not flagged, f"{label}: {method} {path.replace(rid, '{ruta}').replace(lid, '{crédito}').replace(pid, '{pago}').replace(client_id, '{cliente}')} → {res.status_code}",
                  "RESPONDE 2xx: fuga o acción permitida")

    await run(outsider, f"A) otra marca ({outsider.username})")
    await run(julian, "B) cobrador NO asignado a la ruta", skip=("/brands/", "/expensesconcepts/"))

    print("\n== C) cobrador asignado: acciones de administración ==")
    admin_only = [
        ("POST", "/routes/", {"name": "x", "initial_value": 1, "initial_expense": 1, "opening_date": "2026-01-01", "brand_id": str(norte.id), "allowed_users_ids": []}),
        ("PUT", f"/routes/{rid}", {"id": rid, "name": "hack", "initial_value": 1, "initial_expense": 1, "opening_date": "2026-01-01", "allowed_users_ids": [str(carlos.id)]}),
        ("PUT", f"/routes/{rid}/toggle", None),
        ("PUT", f"/users/{laura.id}/toggle", None), ("GET", "/users/", None),
        ("POST", "/brands/", {"name": "x"}),
        ("POST", "/payments/", {"pay_date": "2026-11-07T00:00:00", "payment_date": "2026-11-07T00:00:00", "quota_number": 99, "value": 1, "credit_value": 1, "status": "pagado", "loan_id": lid}),
        ("DELETE", f"/payments/{pid}", None),
        ("PUT", f"/clients/{client_id}/toggle", None),
        ("GET", f"/users/{sup.id}", None),
    ]
    for method, path, body in admin_only:
        kwargs = {"json": body} if body else {}
        res = await safe_call(carlos, method, path, **kwargs)
        check(res.status_code >= 300, f"C) cobrador: {method} {path.replace(rid, '{ruta}').replace(pid, '{pago}').replace(client_id, '{cliente}').replace(str(julian.id), '{usuario}').replace(str(sup.id), '{usuario}').replace(str(norte.id), '{marca}')} → {res.status_code}",
              "El cobrador puede ejecutar una acción de administración")

    failed = [name for ok, name in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN {len(failed)}" if failed else ""))
    for name in failed:
        print("  ✗", name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
