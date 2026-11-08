#!/usr/bin/env python3
"""
QA de Liquidaciones (cierre de caja por cobrador, ruta y día). No borra nada.

Crea rutas nuevas "QD Liq <hora>" (marca NORTE01) con clientes/créditos/cobros/gastos propios y compara la API contra un
cálculo independiente escrito aparte de `liquidation_calculator` (sobre las filas crudas de las tablas): vista previa por
cobrador y consolidada, cierre con faltante, enlace de pagos, doble cierre y concurrencia, cobro posterior ⇒ desactualizado,
confirmar / reabrir / volver a cerrar, permisos por marca, rol y ruta, filtros y paginación, rendimiento.

Uso (contenedor api):  python scripts/qa_liquidations.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytz

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import event, select, text  # noqa: E402

import app.main  # noqa: E402,F401
from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session, engine  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.expense_model import ExpenseConceptModel  # noqa: E402
from app.infrastructure.models.payment_model import PaymentModel  # noqa: E402
from app.infrastructure.models.route_model import RouteModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_reports import RESULTS, TOL, Api, check  # noqa: E402

engine.echo = False
logging.disable(logging.CRITICAL)

STAMP = datetime.now().strftime("%H%M%S")
COUNTER = {"n": 0}
BOGOTA = pytz.timezone("America/Bogota")
ZERO_UUID = "00000000-0000-0000-0000-000000000000"


async def new_route(allowed: list[UUID], brand_id, label: str) -> RouteModel:
    async with async_session() as db:
        route = RouteModel(id=uuid4(), name=f"QD Liq {STAMP} {label}", initial_value=1_000_000, initial_expense=0,
                           opening_date=today_bogota(), brand_id=brand_id, allowed_users_ids=allowed, loans_number=0)
        db.add(route)
        await db.commit()
        return route


async def new_loan(api: Api, user: UserModel, route: RouteModel, *, first_offset: int, value_payment=None, capital=400000):
    COUNTER["n"] += 1
    tag = f"{STAMP}{COUNTER['n']:02d}"
    r = await api.call(user, "POST", "/clients/", json={
        "full_name": f"QD Liq Cliente {tag}", "id_document": f"QD-Z{tag}", "current_address": "Calle QA", "current_phone": "3000000000",
        "current_mobile": "3000000000", "neighborhood": "QA", "linking_date": datetime.now().isoformat(),
        "routes_ids": [str(route.id)], "brand_id": str(user.brand_id)})
    assert r.status_code == 201, r.text
    client = r.json()
    crs = (await api.call(user, "GET", "/clientroute/", params={"route_id": str(route.id)})).json()
    cr = next(c for c in crs if c["client_id"] == client["id"])
    first = today_bogota() + timedelta(days=first_offset)
    body = {"value_quota_fixed": 100000, "agreed_quotas": 6, "date_first_quota": first.isoformat(), "payment_method": "diaria",
            "value_capital": capital, "current_address": "Calle QA", "current_mobile": "3000000000", "clientroute_id": cr["id"], "client_id": client["id"]}
    if value_payment is not None:
        body["value_payment"] = value_payment
    r = await api.call(user, "POST", "/loans/", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def quota(api, user, loan_id, number):
    r = await api.call(user, "GET", "/payments/history", params={"loan_id": loan_id, "page_size": 100})
    return next(i for i in r.json()["items"] if i["quota_number"] == number)


async def pay(api, user, loan_id, number, value):
    q = await quota(api, user, loan_id, number)
    r = await api.call(user, "PUT", f"/payments/{q['id']}/pay", params={"value": value})
    assert r.status_code == 200, r.text
    return q


async def raw_oracle(route_id: UUID, day: date, collector_id: UUID | None) -> dict:
    """Cálculo independiente del cierre sobre filas crudas (sin reutilizar el calculador del backend)."""
    async with async_session() as db:
        pays = (await db.execute(text("""
            SELECT p.id, p.applied, p.value, p.pay_date, p.payment_date, p.collected_by, p.liquidation_id, p.active
            FROM payments p JOIN loans l ON l.id = p.loan_id JOIN clientsroutes cr ON cr.id = l.clientroute_id WHERE cr.route_id = :r"""),
            {"r": route_id})).mappings().all()
        exps = (await db.execute(text("SELECT value, date, created_by, liquidation_id, active FROM expenses WHERE route_id = :r"), {"r": route_id})).mappings().all()
        loans = (await db.execute(text("""
            SELECT l.value_capital, l.created_at, l.created_by, l.active FROM loans l JOIN clientsroutes cr ON cr.id = l.clientroute_id WHERE cr.route_id = :r"""),
            {"r": route_id})).mappings().all()
    mine = [p for p in pays if p["active"] and p["payment_date"] == day and float(p["applied"] or 0) > 0 and p["liquidation_id"] is None
            and (collector_id is None or p["collected_by"] == collector_id)]
    out = {
        "goal": sum(float(p["value"] or 0) for p in pays if p["active"] and p["pay_date"] == day),
        "collected_total": sum(float(p["applied"]) for p in mine),
        "receipts_count": len(mine),
        "collected_due_today": sum(float(p["applied"]) for p in mine if p["pay_date"] == day),
        "collected_overdue": sum(float(p["applied"]) for p in mine if p["pay_date"] < day),
        "partial_count": sum(1 for p in mine if float(p["applied"]) < float(p["value"]) - 0.01),
        "beak_generated": sum(max(float(p["applied"]) - float(p["value"]), 0) for p in mine),
        "expenses_total": sum(float(e["value"]) for e in exps if e["active"] and e["date"] == day and e["liquidation_id"] is None
                              and (collector_id is None or e["created_by"] == collector_id)),
    }
    new = [ln for ln in loans if ln["active"] and ln["created_at"].astimezone(BOGOTA).date() == day and (collector_id is None or ln["created_by"] == collector_id)]
    out["new_loans_total"] = sum(float(ln["value_capital"]) for ln in new)
    out["new_loans_count"] = len(new)
    return out


FIELDS = ["goal", "collected_total", "receipts_count", "collected_due_today", "collected_overdue", "partial_count", "beak_generated",
          "expenses_total", "new_loans_total", "new_loans_count"]


def same(api_data: dict, oracle: dict) -> list[str]:
    return [f"{k}: API {api_data[k]} vs oráculo {oracle[k]}" for k in FIELDS if abs(float(api_data[k]) - float(oracle[k])) > TOL]


def body_for(route, base, cash, **extra):
    return {"route_id": str(route.id), "date": today_bogota().isoformat(), "value_base_delivered": base, "cash_delivered": cash, **extra}


async def main() -> int:
    api = Api()
    today = today_bogota()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        concept = (await db.execute(select(ExpenseConceptModel).where(ExpenseConceptModel.concept == "Combustible", ExpenseConceptModel.brand_id == norte.id))).scalars().first()
    sup, carlos, julian, laura = users["super_norte"], users["qd_carlos"], users["qd_julian"], users["qd_laura"]
    other = next((u for u in users.values() if u.brand_id and u.brand_id != norte.id and u.type_user.value != "01"), None)

    route = await new_route([carlos.id, julian.id], norte.id, "A")
    route2 = await new_route([carlos.id], norte.id, "B")

    print("== 1. Escenario: dos cobradores en la misma ruta ==")
    la = await new_loan(api, carlos, route, first_offset=0, value_payment=100000)       # Carlos: crédito nuevo + cobro de la cuota de hoy
    lb = await new_loan(api, sup, route, first_offset=-3)                                # cuotas ya vencidas
    lc = await new_loan(api, sup, route, first_offset=0)
    ld = await new_loan(api, sup, route, first_offset=0)
    await pay(api, carlos, lb["id"], 1, 100000)                                          # Carlos cobra una cuota ATRASADA hoy
    await pay(api, julian, lc["id"], 1, 40000)                                           # Julián: abono parcial
    await pay(api, julian, ld["id"], 1, 130000)                                          # Julián: pago de más (+30.000 a favor)
    for user, value in ((carlos, 20000), (julian, 5000)):
        r = await api.call(user, "POST", "/expenses/", json={"date": today.isoformat(), "value": value, "name": f"QA gasto {user.username}",
                                                              "expensesconcept_id": str(concept.id), "route_id": str(route.id)})
        assert r.status_code == 201, r.text

    print("== 2. Vista previa vs cálculo independiente ==")
    for label, who, as_user in (("Carlos", carlos, carlos), ("Julián", julian, julian), ("consolidado (admin)", None, sup)):
        params = {"route_id": str(route.id), "date": today.isoformat()}
        if who and as_user is sup:
            params["collector_id"] = str(who.id)
        r = await api.call(as_user, "GET", "/liquidations/preview", params=params)
        ok = r.status_code == 200
        problems = same(r.json(), await raw_oracle(route.id, today, who.id if who else None)) if ok else [r.text[:150]]
        check(ok and not problems, f"vista previa de {label} == cálculo independiente", "; ".join(problems[:4]))
    pc = (await api.call(carlos, "GET", "/liquidations/preview", params={"route_id": str(route.id)})).json()
    check(abs(pc["collected_total"] - 200000) <= TOL and abs(pc["collected_overdue"] - 100000) <= TOL, "la cuota atrasada cobrada hoy SÍ entra al cierre de hoy (Carlos: $200.000)", str(pc["collected_total"]))
    check(abs(pc["new_loans_total"] - 400000) <= TOL and abs(pc["expenses_total"] - 20000) <= TOL, "créditos nuevos y gastos atribuidos a Carlos (400.000 / 20.000)")
    pj = (await api.call(julian, "GET", "/liquidations/preview", params={"route_id": str(route.id)})).json()
    check(abs(pj["beak_generated"] - 30000) <= TOL and pj["partial_count"] == 1 and abs(pj["collected_total"] - 170000) <= TOL, "Julián: $170.000 con 1 parcial y $30.000 de excedente a favor")

    print("== 3. Cierre con cuadre ==")
    expected = 600000 + 200000 - 20000 - 400000                                        # base 50.000 + recaudo − gastos − créditos nuevos
    r = await api.call(carlos, "POST", "/liquidations/", json=body_for(route, 600000, expected - 10000, note="falta un billete"))
    check(r.status_code == 201, "Carlos cierra su caja (201)", r.text[:200])
    liq = r.json()
    check(abs(liq["expected_cash"] - expected) <= TOL and abs(liq["difference"] + 10000) <= TOL and liq["status"] == "pendiente",
          f"esperado ${expected:,.0f}, entregado −10.000 ⇒ diferencia −$10.000 (faltante), estado pendiente", str(liq))
    check(liq["collector_id"] == str(carlos.id) and abs(liq["total_value_charged"] - 200000) <= TOL and liq["receipts_count"] == 2, "el cierre guarda cobrador, recaudo y nº de recibos")
    async with async_session() as db:
        linked = (await db.execute(select(PaymentModel.collected_by).where(PaymentModel.liquidation_id == UUID(liq["id"])))).scalars().all()
        julian_free = (await db.execute(text("SELECT count(*) FROM payments p JOIN loans l ON l.id=p.loan_id JOIN clientsroutes cr ON cr.id=l.clientroute_id WHERE cr.route_id=:r AND p.collected_by=:j AND p.liquidation_id IS NULL AND p.applied>0"), {"r": route.id, "j": julian.id})).scalar_one()
        date_liq = (await db.execute(select(PaymentModel.date_liquidated).where(PaymentModel.liquidation_id == UUID(liq["id"])).limit(1))).scalar_one()
    check(len(linked) == 2 and all(c == carlos.id for c in linked) and julian_free == 2, "solo se enlazan los pagos de Carlos; los de Julián siguen libres")
    check(date_liq == today, "date_liquidated usa la fecha de Colombia", str(date_liq))
    r2 = await api.call(carlos, "POST", "/liquidations/", json=body_for(route, 600000, 0))
    check(r2.status_code == 409, "segundo cierre de Carlos el mismo día → 409", str(r2.status_code))
    pc2 = (await api.call(carlos, "GET", "/liquidations/preview", params={"route_id": str(route.id)})).json()
    check(pc2["collected_total"] == 0 and pc2["existing_liquidation_id"] == liq["id"], "la vista previa ya muestra el cierre existente y no vuelve a sumar lo liquidado")
    res = await asyncio.gather(*[api.call(julian, "POST", "/liquidations/", json=body_for(route, 0, 170000 - 5000)) for _ in range(2)], return_exceptions=True)
    codes = sorted(getattr(x, "status_code", 0) for x in res)
    check(codes == [201, 409], "dos cierres simultáneos de Julián: uno 201 y otro 409", str(codes))
    jl = next(x.json() for x in res if getattr(x, "status_code", 0) == 201)
    check(abs(jl["difference"]) <= TOL, "Julián entrega exacto (170.000 − gasto 5.000 − 0) ⇒ diferencia 0", str(jl["difference"]))

    print("== 4. Cobro posterior ⇒ desactualizado ⇒ reabrir ⇒ volver a cerrar ==")
    await pay(api, carlos, lb["id"], 2, 100000)                                          # nuevo cobro de Carlos DESPUÉS de cerrar
    d = (await api.call(carlos, "GET", f"/liquidations/{liq['id']}")).json()
    check(d["outdated"] is True and abs(d["current_total_charged"] - 300000) <= TOL, "el detalle marca 'desactualizado' y muestra lo vigente ($300.000)", str(d["outdated"]))
    check(len(d["payments"]) == 3, "el detalle lista los recibos del cierre (incluye el nuevo, aún sin enlazar)")
    r = await api.call(sup, "POST", f"/liquidations/{liq['id']}/confirm")
    check(r.status_code == 409, "no se puede confirmar un cierre desactualizado → 409", f"{r.status_code} {r.text[:100]}")
    r = await api.call(carlos, "POST", f"/liquidations/{liq['id']}/reopen")
    check(r.status_code == 403, "un cobrador no puede reabrir → 403", str(r.status_code))
    r = await api.call(sup, "POST", f"/liquidations/{liq['id']}/reopen")
    check(r.status_code == 200 and r.json()["status"] == "reabierta", "el admin reabre el cierre", r.text[:150])
    async with async_session() as db:
        still = (await db.execute(select(PaymentModel.id).where(PaymentModel.liquidation_id == UUID(liq["id"])))).scalars().all()
    check(not still, "reabrir libera todos los pagos del cierre")
    pc3 = (await api.call(carlos, "GET", "/liquidations/preview", params={"route_id": str(route.id)})).json()
    check(abs(pc3["collected_total"] - 300000) <= TOL, "la nueva vista previa de Carlos ya incluye los $300.000", str(pc3["collected_total"]))
    expected2 = 600000 + 300000 - 20000 - 400000
    r = await api.call(carlos, "POST", "/liquidations/", json=body_for(route, 600000, expected2))
    check(r.status_code == 201 and abs(r.json()["difference"]) <= TOL, "Carlos vuelve a cerrar con el total correcto y diferencia 0", r.text[:150])
    liq2 = r.json()
    r = await api.call(sup, "POST", f"/liquidations/{liq2['id']}/confirm")
    check(r.status_code == 200 and r.json()["status"] == "confirmada" and r.json()["confirmed_by_name"], "el admin confirma el cierre", r.text[:150])
    r = await api.call(sup, "POST", f"/liquidations/{liq2['id']}/confirm")
    check(r.status_code == 409, "confirmar dos veces → 409")
    check((await api.call(carlos, "PUT", f"/liquidations/{liq2['id']}", json={"note": "x"})).status_code == 409, "un cierre confirmado no se edita → 409")
    check((await api.call(carlos, "DELETE", f"/liquidations/{liq2['id']}")).status_code == 409, "un cierre confirmado no se elimina (hay que reabrirlo) → 409")
    r = await api.call(julian, "DELETE", f"/liquidations/{jl['id']}")
    async with async_session() as db:
        freed = (await db.execute(text("SELECT count(*) FROM payments WHERE collected_by=:j AND liquidation_id IS NULL AND liquidated = false AND applied>0 AND payment_date=:d"), {"j": julian.id, "d": today})).scalar_one()
    check(r.status_code == 204 and freed >= 2, "un cobrador elimina su cierre pendiente y se liberan sus pagos", f"{r.status_code} libres={freed}")

    print("== 5. Permisos ==")
    check((await api.call(laura, "POST", "/liquidations/", json=body_for(route, 0, 0))).status_code == 403, "el socio no puede cerrar caja → 403")
    check((await api.call(julian, "GET", "/liquidations/preview", params={"route_id": str(route2.id)})).status_code == 403, "un cobrador no asignado a la ruta no ve ni cierra → 403")
    check((await api.call(julian, "POST", "/liquidations/", json=body_for(route2, 0, 0))).status_code == 403, "cobrador no asignado: cerrar caja → 403")
    check((await api.call(julian, "GET", f"/liquidations/{liq2['id']}")).status_code == 404, "un cobrador no puede leer el cierre de otro cobrador → 404")
    check((await api.call(julian, "POST", "/liquidations/", json=body_for(route, 0, 0, collector_id=str(carlos.id)))).status_code == 403, "un cobrador no puede cerrar a nombre de otro → 403")
    check((await api.call(sup, "POST", "/liquidations/", json=body_for(route, 0, 0, date=(today + timedelta(days=2)).isoformat()))).status_code == 400, "no se puede cerrar una fecha futura → 400")
    check((await api.call(sup, "POST", f"/liquidations/{liq2['id']}/confirm")).status_code == 409, "(control) estado actual coherente")
    if other:
        check((await api.call(other, "GET", f"/liquidations/{liq2['id']}")).status_code == 404, f"otra marca ({other.username}) no lee el cierre → 404")
        check((await api.call(other, "POST", f"/liquidations/{liq2['id']}/reopen")).status_code in (403, 404), "otra marca no reabre")
        lo = await api.call(other, "GET", "/liquidations/")
        check(lo.status_code == 200 and all(i["id"] != liq2["id"] for i in lo.json()["items"]), "el listado de otra marca no incluye mis cierres")
    r = await api.call(julian, "GET", "/liquidations/")
    check(r.status_code == 200 and all(i["collector_id"] == str(julian.id) for i in r.json()["items"]), "el listado del cobrador solo trae sus cierres")
    r = await api.call(sup, "GET", "/liquidations/", params={"route_id": str(route.id), "status": "reabierta"})
    check(r.status_code == 200 and r.json()["total"] >= 1 and all(i["status"] == "reabierta" for i in r.json()["items"]), "filtro de estado 'reabierta' funciona")
    r = await api.call(sup, "GET", "/liquidations/", params={"route_id": str(route.id), "status": "confirmada"})
    check(r.status_code == 200 and any(i["id"] == liq2["id"] for i in r.json()["items"]), "filtro de estado 'confirmada' funciona")

    print("== 6. Admin: consolidado ==")
    rc = await api.call(sup, "POST", "/liquidations/", json=body_for(route, 0, 0, collector_id=str(julian.id)))
    check(rc.status_code == 201, "el admin cierra a nombre de un cobrador asignado", rc.text[:120])
    check((await api.call(sup, "POST", "/liquidations/", json=body_for(route, 0, 0, collector_id=str(laura.id)))).status_code == 400, "el admin no puede cerrar a nombre de alguien no asignado a la ruta → 400")
    r = await api.call(sup, "GET", "/liquidations/", params={"route_id": str(route.id), "page_size": 1})
    body = r.json()
    check(r.status_code == 200 and body["total"] >= 2 and len(body["items"]) == 1 and body["pages"] >= 2, "el listado del admin está paginado y filtra por ruta", str(body["total"]))

    print("== 7. Rendimiento ==")
    statements = []

    def on_exec(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", on_exec)
    start = time.perf_counter()
    await api.call(carlos, "GET", "/liquidations/preview", params={"route_id": str(route.id)})
    preview_ms, preview_n = (time.perf_counter() - start) * 1000, len(statements)
    statements.clear()
    r3 = await new_route([carlos.id], norte.id, "C")
    await new_loan(api, carlos, r3, first_offset=0, value_payment=100000)
    statements.clear()
    start = time.perf_counter()
    r = await api.call(carlos, "POST", "/liquidations/", json=body_for(r3, 400000, 100000))
    close_ms, close_n = (time.perf_counter() - start) * 1000, len(statements)
    event.remove(engine.sync_engine, "before_cursor_execute", on_exec)
    print(f"      vista previa: {preview_n} sentencias, {preview_ms:.0f} ms · cierre: {close_n} sentencias, {close_ms:.0f} ms")
    check(r.status_code == 201 and preview_n <= 12 and close_n <= 18, "vista previa ≤ 12 y cierre ≤ 18 sentencias SQL (sin traer filas a Python)", f"{preview_n}/{close_n}")

    failed = [name for ok, name in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
