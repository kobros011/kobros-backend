#!/usr/bin/env python3
"""
QA de la prioridad (orden) de clientes por ruta y de clientes en varias rutas.

Crea dos rutas nuevas y clientes (uno en las dos rutas) con la API y comprueba que:
  * un cliente en varias rutas queda vinculado a TODAS y su prioridad es independiente en cada una;
  * mover uno, mover varios (bulk) y fijar el orden completo dejan prioridades 1..n sin repetidos ni huecos;
  * dos movimientos simultáneos no corrompen el orden;
  * quitar y agregar rutas a un cliente compacta/continúa la numeración;
  * solo administración mueve (cobrador 403, otra marca 404) y `ClientRead.routes` trae la prioridad por ruta.
No borra nada (datos "QD Ord").

Uso (contenedor api):  python scripts/qa_client_order.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_liquidations import STAMP, new_route  # noqa: E402
from scripts.qa_reports import RESULTS, Api, check  # noqa: E402

COUNTER = {"n": 0}


async def new_client(api: Api, user: UserModel, route_ids: list, label: str) -> dict:
    COUNTER["n"] += 1
    tag = f"{STAMP}{COUNTER['n']:02d}"
    r = await api.call(user, "POST", "/clients/", json={
        "full_name": f"QD Ord {label} {tag}", "id_document": f"QD-O{tag}", "current_address": "Calle QA", "current_phone": "3000000000",
        "current_mobile": "3000000000", "neighborhood": "QA", "linking_date": datetime.now().isoformat(),
        "routes_ids": [str(x) for x in route_ids], "brand_id": str(user.brand_id)})
    assert r.status_code == 201, r.text
    return r.json()


async def route_rows(api: Api, user: UserModel, route_id) -> list[dict]:
    r = await api.call(user, "GET", "/clientroute/", params={"route_id": str(route_id)})
    assert r.status_code == 200, r.text
    return r.json()


def contiguous(rows: list[dict]) -> bool:
    return [x["order"] for x in rows] == list(range(1, len(rows) + 1))


async def main() -> int:
    api = Api()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
    sup, carlos = users["super_norte"], users["qd_carlos"]
    outsider = next((u for u in users.values() if u.brand_id and u.brand_id != norte.id and u.type_user.value in ("02", "03")), None)

    route_a = await new_route([carlos.id], norte.id, "ORD-A")
    route_b = await new_route([carlos.id], norte.id, "ORD-B")
    a, b = str(route_a.id), str(route_b.id)

    print("== Cliente en varias rutas ==")
    multi = await new_client(api, sup, [route_a.id, route_b.id], "multi")
    c2 = await new_client(api, sup, [route_a.id], "dos")
    c3 = await new_client(api, sup, [route_a.id], "tres")
    c4 = await new_client(api, sup, [route_a.id], "cuatro")
    rows_a, rows_b = await route_rows(api, sup, a), await route_rows(api, sup, b)
    check(len(rows_a) == 4 and contiguous(rows_a), "ruta A: 4 clientes con prioridades 1..4")
    check(len(rows_b) == 1 and rows_b[0]["client_id"] == multi["id"] and rows_b[0]["order"] == 1, "el cliente multi-ruta también quedó en la ruta B (#1)")
    detail = (await api.call(sup, "GET", f"/clients/{multi['id']}")).json()
    check({x["route_id"] for x in detail["routes"]} == {a, b} and len(detail["routes_ids"]) == 2, "ClientRead.routes trae sus 2 rutas con prioridad")

    by_client = {r["client_id"]: r for r in rows_a}
    cr = {name: by_client[c["id"]]["id"] for name, c in (("multi", multi), ("c2", c2), ("c3", c3), ("c4", c4))}

    print("== Datos para la UI ==")
    ra = {x["client_id"]: x for x in rows_a}
    check(all(x["route_name"] for x in rows_a) and ra[c2["id"]]["neighborhood"] == "QA" and ra[c2["id"]]["current_mobile"] == "3000000000" and ra[c2["id"]]["client_active"] is True,
          "ClientRouteRead trae ruta, barrio, celular y estado del cliente")
    totals = {x["route_id"]: x["route_total"] for x in detail["routes"]}
    check(totals == {a: 4, b: 1}, f"ClientRead.routes trae route_total por ruta (A=4, B=1) -> {totals}")
    listing = (await api.call(sup, "GET", "/clients/", params={"route_id": a, "page_size": 50})).json()
    listing = listing["items"] if isinstance(listing, dict) else listing
    mine = [it["id"] for it in listing if it["id"] in {multi["id"], c2["id"], c3["id"], c4["id"]}]
    check(mine == [multi["id"], c2["id"], c3["id"], c4["id"]], "GET /clients?route_id= ordena por la prioridad de esa ruta")

    print("== Mover uno ==")
    r = await api.call(sup, "PUT", f"/clientroute/{cr['c4']}/order", json={"position": 1})
    rows = r.json() if r.status_code == 200 else []
    check(r.status_code == 200 and contiguous(rows) and rows[0]["client_id"] == c4["id"], "mover al #1 recorre a los demás sin duplicados", r.text[:120])
    check([x["client_id"] for x in rows] == [c4["id"], multi["id"], c2["id"], c3["id"]], "orden resultante: c4, multi, c2, c3")
    check((await route_rows(api, sup, b))[0]["order"] == 1, "la prioridad del cliente en la ruta B no cambió")
    r = await api.call(sup, "PUT", f"/clientroute/{cr['c4']}/order", json={"position": 99})
    rows = r.json()
    check(r.status_code == 200 and rows[-1]["client_id"] == c4["id"] and contiguous(rows), "una posición mayor al total lo deja al final")

    print("== Mover varios ==")
    r = await api.call(sup, "POST", "/clientroute/bulk-move", json={"route_id": a, "clientroute_ids": [cr["c3"], cr["multi"]], "target": "start"})
    rows = r.json()
    check(r.status_code == 200 and [x["client_id"] for x in rows[:2]] == [multi["id"], c3["id"]] and contiguous(rows), "bulk al inicio conserva su orden relativo")
    r = await api.call(sup, "POST", "/clientroute/bulk-move", json={"route_id": a, "clientroute_ids": [cr["multi"]], "target": "position", "position": 3})
    rows = r.json()
    check(r.status_code == 200 and rows[2]["client_id"] == multi["id"] and contiguous(rows), "bulk a la posición #3")
    r = await api.call(sup, "POST", "/clientroute/bulk-move", json={"route_id": a, "clientroute_ids": [cr["c2"]], "target": "position"})
    check(r.status_code in (400, 422), "bulk con 'position' sin número se rechaza", str(r.status_code))
    other = (await route_rows(api, sup, b))[0]["id"]
    r = await api.call(sup, "POST", "/clientroute/bulk-move", json={"route_id": a, "clientroute_ids": [other], "target": "end"})
    check(r.status_code == 400, "no se puede mover un cliente de otra ruta dentro de esta", str(r.status_code))

    print("== Orden completo ==")
    current = [x["id"] for x in await route_rows(api, sup, a)]
    r = await api.call(sup, "PUT", "/clientroute/reorder", json={"route_id": a, "ordered_ids": list(reversed(current))})
    rows = r.json()
    check(r.status_code == 200 and [x["id"] for x in rows] == list(reversed(current)) and contiguous(rows), "reorder fija exactamente el orden pedido")
    r = await api.call(sup, "PUT", "/clientroute/reorder", json={"route_id": a, "ordered_ids": current[:-1]})
    check(r.status_code == 409, "reorder con la lista incompleta → 409 (la ruta cambió)", str(r.status_code))

    print("== Concurrencia ==")
    ids = [x["id"] for x in await route_rows(api, sup, a)]
    calls = [api.call(sup, "PUT", f"/clientroute/{ids[i]}/order", json={"position": 1}) for i in range(len(ids))]
    results = await asyncio.gather(*calls, return_exceptions=True)
    ok = [x for x in results if not isinstance(x, Exception) and x.status_code == 200]
    final = await route_rows(api, sup, a)
    check(len(ok) == len(ids) and contiguous(final) and len({x["order"] for x in final}) == len(final), f"{len(ids)} movimientos simultáneos dejan prioridades 1..n sin repetidos")

    print("== Rutas del cliente ==")
    r = await api.call(sup, "PUT", f"/clients/{multi['id']}", json={"id": multi["id"], "full_name": multi["full_name"], "routes_ids": [a]})
    detail = (await api.call(sup, "GET", f"/clients/{multi['id']}")).json()
    check(r.status_code == 200 and [x["route_id"] for x in detail["routes"]] == [a], "quitar la ruta B (sin créditos) deja solo la A", r.text[:120])
    check(len(await route_rows(api, sup, b)) == 0, "la ruta B queda sin ese cliente")
    r = await api.call(sup, "PUT", f"/clients/{multi['id']}", json={"id": multi["id"], "full_name": multi["full_name"], "routes_ids": [a, b]})
    rows_b = await route_rows(api, sup, b)
    check(r.status_code == 200 and len(rows_b) == 1 and rows_b[0]["order"] == 1, "volver a agregar la ruta B lo deja al final (#1 en una ruta vacía)")
    r = await api.call(sup, "PUT", f"/clients/{multi['id']}", json={"id": multi["id"], "full_name": multi["full_name"], "routes_ids": []})
    check(r.status_code == 400, "un cliente no puede quedar sin rutas → 400", str(r.status_code))
    cr_b = rows_b[0]["id"]
    loan = await api.call(sup, "POST", "/loans/", json={"value_quota_fixed": 100000, "agreed_quotas": 6, "date_first_quota": datetime.now().date().isoformat(), "payment_method": "diaria",
                                                       "value_capital": 400000, "current_address": "Calle QA", "current_mobile": "3000000000", "clientroute_id": cr_b, "client_id": multi["id"]})
    check(loan.status_code == 201, "se crea un crédito del cliente en la ruta B", loan.text[:120])
    r = await api.call(sup, "PUT", f"/clients/{multi['id']}", json={"id": multi["id"], "full_name": multi["full_name"], "routes_ids": [a]})
    check(r.status_code == 409, "no se puede quitar una ruta donde el cliente tiene un crédito con saldo → 409", f"{r.status_code} {r.text[:100]}")
    check(len(await route_rows(api, sup, b)) == 1, "la ruta B sigue con su cliente tras el intento rechazado")
    r = await api.call(carlos, "PUT", f"/clients/{multi['id']}", json={"id": multi["id"], "full_name": multi["full_name"], "routes_ids": [a]})
    check(r.status_code in (403, 404), "un cobrador no puede cambiar las rutas del cliente", str(r.status_code))
    r = await api.call(carlos, "PUT", f"/clients/{multi['id']}", json={"id": multi["id"], "full_name": multi["full_name"], "routes_ids": [a, b]})
    check(r.status_code == 200, "un cobrador sí puede guardar al cliente si las rutas no cambian (el formulario las reenvía)", str(r.status_code))

    print("== Permisos ==")
    r = await api.call(carlos, "PUT", f"/clientroute/{cr['c2']}/order", json={"position": 1})
    check(r.status_code == 403, "el cobrador no puede mover prioridades → 403", str(r.status_code))
    r = await api.call(carlos, "POST", "/clientroute/bulk-move", json={"route_id": a, "clientroute_ids": [cr["c2"]], "target": "start"})
    check(r.status_code == 403, "el cobrador no puede mover en bloque → 403", str(r.status_code))
    check((await api.call(carlos, "GET", "/clientroute/", params={"route_id": a})).status_code == 200, "el cobrador sí puede ver las prioridades de su ruta")
    if outsider:
        r = await api.call(outsider, "PUT", f"/clientroute/{cr['c2']}/order", json={"position": 1})
        check(r.status_code == 404, f"otra marca ({outsider.username}) no puede mover → 404", str(r.status_code))
        r = await api.call(outsider, "PUT", "/clientroute/reorder", json={"route_id": a, "ordered_ids": [cr["c2"]]})
        check(r.status_code == 404, "otra marca no puede reordenar la ruta → 404", str(r.status_code))
    stable = await route_rows(api, sup, a)
    check(contiguous(stable), "tras los intentos rechazados el orden sigue 1..n")

    failed = [name for ok_, name in RESULTS if not ok_]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN {len(failed)}" if failed else ""))
    for name in failed:
        print("  ✗", name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
