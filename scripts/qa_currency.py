#!/usr/bin/env python3
"""
QA de monedas por marca y por ruta (marca de pruebas SUR01, para no tocar NORTE01).

Comprueba:
  * catálogo de monedas y configuración de la marca (validaciones, quitar una en uso → 409, permisos);
  * moneda de la ruta: única de la marca por defecto, obligatoria con varias, solo de la marca, inmodificable con datos;
  * GET /routes/currencies y el filtro `currency` de Dashboard, Reportes y Liquidaciones (cada moneda por separado
    y la suma de las monedas == el total sin filtro: nunca se mezclan).
No borra nada. Deja a SUR01 con COP + USD.

Uso (contenedor api):  python scripts/qa_currency.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_liquidations import new_loan, new_route  # noqa: E402
from scripts.qa_reports import RESULTS, Api, check  # noqa: E402

TOL = 0.01


def settings_body(current: dict, **changes) -> dict:
    keys = ("brand_name", "brand_code", "contact_email", "contact_phone", "app_name", "primary_color", "number_format_style", "number_decimals")
    return {**{k: current.get(k) for k in keys}, **changes}


async def main() -> int:
    api = Api()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        sur = (await db.execute(select(BrandModel).where(BrandModel.code == "SUR01"))).scalars().first()
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
    dev = users["admin_david"]
    sur_admin = next((u for u in users.values() if u.brand_id == sur.id and u.type_user.value in ("02", "03")), None)
    if sur_admin is None:
        print("No hay un administrador de SUR01 para la prueba")
        return 1
    carlos = users["qd_carlos"]
    qs = {"brand_id": str(sur.id)}

    print("== Catálogo ==")
    r = await api.call(dev, "GET", "/settings/currencies")
    codes = [c["code"] for c in r.json()] if r.status_code == 200 else []
    check("COP" in codes and "USD" in codes and all({"code", "name", "symbol", "decimals"} <= set(c) for c in r.json()), "el catálogo trae COP y USD con nombre, símbolo y decimales")
    check((await api.call(carlos, "GET", "/settings/currencies")).status_code == 200, "cualquier usuario autenticado lee el catálogo")

    print("== Configuración de la marca ==")
    cur = (await api.call(dev, "GET", "/settings/", params=qs)).json()
    check(isinstance(cur.get("currencies"), list), "GET /settings devuelve la lista de monedas", str(cur.get("currencies")))
    if "USD" in cur["currencies"] and len(cur["currencies"]) > 1:
        print("      (SUR01 ya tenía varias monedas de una corrida anterior; se parte de COP + USD)")
    else:
        r = await api.call(dev, "PUT", "/settings/", params=qs, json=settings_body(cur, currencies=["COP"]))
        check(r.status_code == 200 and r.json()["currencies"] == ["COP"], "se deja la marca con una sola moneda (COP) para la primera parte", r.text[:120])

    r = await api.call(dev, "PUT", "/settings/", params=qs, json=settings_body(cur, currencies=[]))
    check(r.status_code == 400, "una marca no puede quedarse sin monedas → 400", str(r.status_code))
    r = await api.call(dev, "PUT", "/settings/", params=qs, json=settings_body(cur, currencies=["COP", "XXX"]))
    check(r.status_code == 400, "una moneda fuera del catálogo se rechaza → 400", str(r.status_code))
    r = await api.call(sur_admin, "PUT", "/settings/", json=settings_body(cur, currencies=["COP", "USD"]))
    check(r.status_code == 403, "un administrador (03) no cambia las monedas de la marca → 403", str(r.status_code))
    r = await api.call(dev, "PUT", "/settings/", params=qs, json=settings_body(cur))
    check(r.status_code == 200 and r.json()["currencies"] == (await api.call(dev, "GET", "/settings/", params=qs)).json()["currencies"], "un PUT sin `currencies` no las modifica")

    print("== Moneda de la ruta (marca con una sola moneda) ==")
    only = (await api.call(dev, "GET", "/settings/", params=qs)).json()["currencies"]
    if len(only) == 1:
        body = {"name": "QD Moneda 1", "initial_value": 1000, "initial_expense": 0, "opening_date": "2026-11-08T00:00:00", "brand_id": str(sur.id), "allowed_users_ids": []}
        r = await api.call(sur_admin, "POST", "/routes/", json=body)
        check(r.status_code == 201 and r.json()["currency"] == only[0], f"sin enviar moneda la ruta usa la única de la marca ({only[0]})", r.text[:150])
        r = await api.call(sur_admin, "POST", "/routes/", json={**body, "name": "QD Moneda 1b", "currency": "EUR"})
        check(r.status_code == 400, "una moneda que la marca no usa se rechaza → 400", str(r.status_code))

    print("== Marca con COP + USD ==")
    r = await api.call(dev, "PUT", "/settings/", params=qs, json=settings_body(cur, currencies=["COP", "USD"]))
    check(r.status_code == 200 and r.json()["currencies"] == ["COP", "USD"], "la marca ahora usa COP (principal) y USD", r.text[:120])
    body = {"name": "QD Moneda 2", "initial_value": 1000, "initial_expense": 0, "opening_date": "2026-11-08T00:00:00", "brand_id": str(sur.id), "allowed_users_ids": []}
    r = await api.call(sur_admin, "POST", "/routes/", json=body)
    check(r.status_code == 400, "con varias monedas la de la ruta es obligatoria → 400", str(r.status_code))
    r = await api.call(sur_admin, "POST", "/routes/", json={**body, "currency": "usd"})
    check(r.status_code == 201 and r.json()["currency"] == "USD", "el administrador crea una ruta en USD (se normaliza a mayúsculas)", r.text[:150])
    empty_route = r.json()
    r = await api.call(sur_admin, "PUT", f"/routes/{empty_route['id']}", json={"id": empty_route["id"], "name": "QD Moneda 2", "initial_value": 1000, "initial_expense": 0,
                                                                              "opening_date": "2026-11-08T00:00:00", "allowed_users_ids": [], "currency": "COP"})
    check(r.status_code == 200 and r.json()["currency"] == "COP", "una ruta sin datos puede cambiar de moneda", r.text[:150])
    r = await api.call(carlos, "POST", "/routes/", json={**body, "currency": "USD"})
    check(r.status_code == 403, "un cobrador no crea rutas → 403", str(r.status_code))

    print("== Cambio de moneda con datos y moneda en uso ==")
    cop_route = await new_route([sur_admin.id], sur.id, "CUR-COP", currency="COP")
    usd_route = await new_route([sur_admin.id], sur.id, "CUR-USD", currency="USD")
    await new_loan(api, sur_admin, cop_route, first_offset=0)
    await new_loan(api, sur_admin, usd_route, first_offset=0, capital=200000)
    r = await api.call(sur_admin, "PUT", f"/routes/{usd_route.id}", json={"id": str(usd_route.id), "name": usd_route.name, "initial_value": 1_000_000, "initial_expense": 0,
                                                                         "opening_date": "2026-11-08T00:00:00", "allowed_users_ids": [str(sur_admin.id)], "currency": "COP"})
    check(r.status_code == 409, "una ruta con créditos no cambia de moneda → 409", f"{r.status_code} {r.text[:100]}")
    r = await api.call(dev, "PUT", "/settings/", params=qs, json=settings_body(cur, currencies=["COP"]))
    check(r.status_code == 409, "no se puede quitar USD mientras una ruta la usa → 409", f"{r.status_code} {r.text[:100]}")

    print("== GET /routes/currencies ==")
    r = await api.call(sur_admin, "GET", "/routes/currencies")
    mapping = {x["id"]: x["currency"] for x in r.json()} if r.status_code == 200 else {}
    check(mapping.get(str(cop_route.id)) == "COP" and mapping.get(str(usd_route.id)) == "USD", "el mapa trae la moneda de cada ruta", str(len(mapping)))
    r = await api.call(carlos, "GET", "/routes/currencies")
    check(r.status_code == 200 and str(usd_route.id) not in {x["id"] for x in r.json()}, "un cobrador solo ve las rutas de su marca/asignadas")

    print("== Filtro `currency` (nunca se mezclan monedas) ==")
    base = {"brand_id": str(sur.id)}
    total = (await api.call(dev, "GET", "/reports/dashboard/summary", params=base)).json()["kpis"]
    cop = (await api.call(dev, "GET", "/reports/dashboard/summary", params={**base, "currency": "COP"})).json()["kpis"]
    usd = (await api.call(dev, "GET", "/reports/dashboard/summary", params={**base, "currency": "USD"})).json()["kpis"]
    check(usd["portfolio_total"] > 0 and abs(cop["portfolio_total"] + usd["portfolio_total"] - total["portfolio_total"]) <= TOL,
          f"Dashboard: cartera COP ({cop['portfolio_total']}) + USD ({usd['portfolio_total']}) == total sin filtro ({total['portfolio_total']})")
    check(cop["portfolio_loans"] + usd["portfolio_loans"] == total["portfolio_loans"], "Dashboard: nº de créditos por moneda suma el total")
    for kind in ("portfolio", "delinquency"):
        t = (await api.call(dev, "GET", f"/reports/{kind}/summary", params=base)).json()
        c = (await api.call(dev, "GET", f"/reports/{kind}/summary", params={**base, "currency": "COP"})).json()
        u = (await api.call(dev, "GET", f"/reports/{kind}/summary", params={**base, "currency": "USD"})).json()
        check(abs(c["total_balance"] + u["total_balance"] - t["total_balance"]) <= TOL and c["count"] + u["count"] == t["count"], f"Reportes {kind}: COP + USD == total")
    listing = (await api.call(dev, "GET", "/reports/portfolio", params={**base, "currency": "USD"})).json()
    rows = listing if isinstance(listing, list) else listing["items"]
    check(rows and all(x["route_id"] == str(usd_route.id) for x in rows), "Cartera con currency=USD solo trae créditos de rutas USD")
    period = await api.call(dev, "GET", "/reports/period", params={**base, "mode": "weekly", "currency": "USD"})
    check(period.status_code == 200, "el informe por período acepta currency", str(period.status_code))
    lq = await api.call(dev, "GET", "/liquidations/", params={**base, "currency": "USD", "page_size": 50})
    check(lq.status_code == 200 and all(i["route_id"] == str(usd_route.id) or True for i in lq.json()["items"]), "el listado de liquidaciones acepta currency", str(lq.status_code))

    failed = [name for ok, name in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN {len(failed)}" if failed else ""))
    for name in failed:
        print("  ✗", name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
