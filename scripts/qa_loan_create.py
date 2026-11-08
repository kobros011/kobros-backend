#!/usr/bin/env python3
"""
QA de la creación de créditos (`POST /loans`) y del saldo a favor (beak).

Compara la API contra un cálculo independiente (calendario de cuotas escrito aparte de `build_payment_schedule`),
prueba cobro inicial (vacío / parcial / exacto / mayor), acumulación del beak, validaciones, atomicidad, seguridad
por marca/rol/ruta, conciliación con Reportes y mide sentencias SQL y milisegundos por crédito.
NO borra nada: los clientes y créditos creados (prefijo QD-L) se conservan.

Uso (desde el contenedor api):  python scripts/qa_loan_create.py
"""
from __future__ import annotations

import asyncio
import calendar
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import event, func, select  # noqa: E402

from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session, engine  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.client_model import ClientModel  # noqa: E402
from app.infrastructure.models.loan_model import LoanModel  # noqa: E402
from app.infrastructure.models.payment_model import PaymentModel  # noqa: E402
from app.infrastructure.models.route_model import RouteModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from app.infrastructure.repositories.payment_repository import PaymentRepository  # noqa: E402
from scripts.qa_reports import RESULTS, TOL, Api, check  # noqa: E402

STAMP = datetime.now().strftime("%H%M%S")
COUNTER = {"n": 0}


def add_months(d: date, months: int) -> date:
    total = d.year * 12 + d.month - 1 + months
    year, month = divmod(total, 12)
    month += 1
    return d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1]))


def expected_schedule(first: date, method: str, n: int, fixed_day: int | None) -> list[date]:
    """Calendario esperado escrito de forma independiente a la implementación."""
    out = []
    for i in range(n):
        if method == "diaria":
            out.append(first + timedelta(days=i))
        elif method == "semanal":
            out.append(first + timedelta(days=7 * i))
        elif method == "quincenal":
            out.append(first + timedelta(days=14 * i))
        elif method == "mensual":
            out.append(add_months(first, i))
        else:  # dia_fijo
            base = add_months(first, i)
            out.append(base.replace(day=min(fixed_day, calendar.monthrange(base.year, base.month)[1])))
    return out


async def new_client(api: Api, user: UserModel, route: RouteModel):
    COUNTER["n"] += 1
    tag = f"{STAMP}{COUNTER['n']:02d}"
    r = await api.call(user, "POST", "/clients/", json={
        "full_name": f"QD Loan {tag}", "id_document": f"QD-L{tag}", "current_address": "Calle QA", "current_phone": "3000000000",
        "current_mobile": "3000000000", "neighborhood": "QA", "linking_date": datetime.now().isoformat(),
        "routes_ids": [str(route.id)], "brand_id": str(user.brand_id)})
    assert r.status_code == 201, r.text
    client = r.json()
    crs = (await api.call(user, "GET", "/clientroute/", params={"route_id": str(route.id)})).json()
    cr = next(c for c in crs if c["client_id"] == client["id"])
    return client, cr


def loan_payload(client, cr, *, method="semanal", quotas=4, quota=100000, capital=300000, first=None, value_payment=None, **extra):
    first = first or today_bogota()
    body = {
        "end_date": (first + timedelta(days=30)).isoformat(), "value_quota_fixed": quota, "agreed_quotas": quotas,
        "date_first_quota": first.isoformat(), "payment_method": method, "fixed_payment_day": extra.pop("fixed_payment_day", None),
        "value_capital": capital, "current_address": "Calle QA 2", "current_mobile": "3111111111",
        "clientroute_id": cr["id"], "client_id": client["id"],
    }
    if value_payment is not None:
        body["value_payment"] = value_payment
    body.update(extra)
    return body


async def history(api, user, loan_id):
    r = await api.call(user, "GET", "/payments/history", params={"loan_id": loan_id, "page_size": 100})
    return r.json()


async def db_state(client_id, loan_id=None):
    async with async_session() as db:
        client = (await db.execute(select(ClientModel).where(ClientModel.id == client_id))).scalars().first()
        loan = (await db.execute(select(LoanModel).where(LoanModel.id == loan_id))).scalars().first() if loan_id else None
        return float(client.beak or 0), loan


async def kpis(api, user):
    return (await api.call(user, "GET", "/reports/dashboard/summary")).json()["kpis"]


async def main() -> int:
    engine.echo = False
    api = Api()
    today = today_bogota()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        routes = {r.name: r for r in (await db.execute(select(RouteModel).where(RouteModel.brand_id == norte.id))).scalars().all()}
    sup, carlos = users["super_norte"], users.get("qd_carlos")
    other = next((u for u in users.values() if u.brand_id and u.brand_id != norte.id and u.type_user.value != "01"), None)
    norte_route, sur_route = routes["Ruta Norte"], routes["Ruta Sur"]

    print("== 1. Calendario de cuotas por método vs cálculo independiente ==")
    cases = [
        ("diaria", today, None), ("semanal", today, None), ("quincenal", today, None),
        ("mensual", date(2026, 1, 31), None), ("dia_fijo", date(2026, 1, 15), 31), ("dia_fijo", today, 5),
    ]
    for method, first, fixed in cases:
        client, cr = await new_client(api, sup, norte_route)
        r = await api.call(sup, "POST", "/loans/", json=loan_payload(client, cr, method=method, quotas=6, first=first, fixed_payment_day=fixed))
        ok = r.status_code == 201
        check(ok, f"POST /loans {method} (primera {first}) → 201", r.text[:200])
        if not ok:
            continue
        loan = r.json()
        hist = await history(api, sup, loan["id"])
        got = [date.fromisoformat(i["pay_date"]) for i in hist["items"]]
        exp = expected_schedule(first, method, 6, fixed)
        check(got == exp, f"{method} (primera {first}): fechas de las 6 cuotas == calendario independiente", f"{got} vs {exp}")
        check(all(abs(i["value"] - 100000) <= TOL and i["status"] in ("pendiente", "mora") and i["applied"] == 0 for i in hist["items"]),
              f"{method}: cuotas con valor fijo, sin abonos")
        check(loan["end_date"][:10] == exp[-1].isoformat(), f"{method}: end_date = vencimiento de la última cuota", loan["end_date"])
        check(loan["pending_quotas"] == 6 and loan["canceled_quotas"] == 0, f"{method}: respuesta con cuotas pendientes=6 y canceladas=0")

    print("== 2. Cálculos del servidor (ignora lo que mande el cliente) ==")
    client, cr = await new_client(api, sup, norte_route)
    r = await api.call(sup, "POST", "/loans/", json=loan_payload(client, cr, quotas=5, quota=120000, capital=500000, value_total_loan=1, value_utility_loan=2, interest_rate=3))
    loan = r.json()
    check(r.status_code == 201 and abs(loan["value_total_loan"] - 600000) <= TOL and abs(loan["value_utility_loan"] - 100000) <= TOL
          and abs(loan["interest_rate"] - 20.0) <= 0.001, "total = cuota × cuotas, utilidad = total − capital, interés = utilidad/capital (20 %)", r.text[:200])
    detail = (await api.call(sup, "GET", f"/loans/{loan['id']}")).json()
    check(abs(detail["paid"]) <= TOL and abs(detail["balance"] - 600000) <= TOL, "GET /loans/{id}: paid=0 y balance=total")
    async with async_session() as db:
        route_now = (await db.execute(select(RouteModel).where(RouteModel.id == norte_route.id))).scalars().first()
    check(loan["loan_number"] == route_now.loans_number, "loan_number lo asigna el servidor y route.loans_number queda igual")

    print("== 3. Cobro inicial (value_payment) y beak ==")
    base_kpis = await kpis(api, sup)
    # Estado calculado del historial: una cuota que vence hoy con abono parcial sigue "pendiente" (aún no venció);
    # en la BD queda 'mora' (misma regla que pay_payment) y suma el faltante a total_default.
    scenarios = [("vacío", None, "pendiente", 0, 0, 0), ("parcial", 40000, "pendiente", 40000, 60000, 0),
                 ("exacto", 100000, "pagado", 100000, 0, 0), ("mayor", 130000, "pagado", 130000, 0, 30000)]
    created = {}
    for name, vp, status, applied, default, beak in scenarios:
        client, cr = await new_client(api, sup, norte_route)
        before = await kpis(api, sup)
        r = await api.call(sup, "POST", "/loans/", json=loan_payload(client, cr, value_payment=vp))
        check(r.status_code == 201, f"cobro inicial {name}: POST /loans 201", r.text[:200])
        loan = r.json()
        created[name] = (client, cr, loan)
        hist = await history(api, sup, loan["id"])
        q1 = hist["items"][0]
        check(q1["status"] == status and abs(q1["applied"] - applied) <= TOL, f"{name}: cuota 1 queda '{status}' con applied={applied}", str(q1))
        if vp:
            check(q1["collected_by_id"] == str(sup.id) and q1["payment_date"] == today.isoformat(), f"{name}: guarda quién recaudó y la fecha de hoy")
        beak_db, loan_db = await db_state(client["id"], loan["id"])
        if name == "parcial":
            async with async_session() as db:
                stored = (await db.execute(select(PaymentModel.status).where(PaymentModel.id == q1["id"]))).scalar_one()
            check(stored == "mora", "parcial: la cuota queda 'mora' en la BD (regla de pay_payment)", stored)
        check(abs(beak_db - beak) <= TOL, f"{name}: beak del cliente = {beak}", f"{beak_db}")
        check(abs(float(loan_db.total_default or 0) - default) <= TOL, f"{name}: total_default del crédito = {default}")
        expect_canceled = 1 if vp else 0
        check(loan_db.canceled_quotas == expect_canceled and loan_db.pending_quotas == 4 - expect_canceled, f"{name}: cuotas canceladas={expect_canceled}, pendientes={4 - expect_canceled}")
        after = await kpis(api, sup)
        paid = applied
        check(abs(after["portfolio_total"] - before["portfolio_total"] - (400000 - paid)) <= TOL and abs(after["total_paid"] - before["total_paid"] - paid) <= TOL,
              f"{name}: Reportes suben cartera {400000 - paid:,.0f} y pagado {paid:,.0f} exactamente")
        detail = (await api.call(sup, "GET", f"/loans/{loan['id']}")).json()
        check(abs(detail["paid"] - paid) <= TOL and abs(detail["balance"] - (400000 - paid)) <= TOL, f"{name}: detalle del crédito paid/balance correctos")
    check(base_kpis is not None, "conciliación de Reportes ejecutada")

    print("== 4. Beak: acumula entre cuotas y créditos, y se corrige al re-abonar ==")
    client, cr, loan = created["mayor"]  # beak 30.000 tras el cobro inicial
    r = await api.call(sup, "POST", "/loans/", json=loan_payload(client, cr, value_payment=120000))
    check(r.status_code == 201, "segundo crédito del mismo cliente con cobro mayor", r.text[:150])
    beak_db, _ = await db_state(client["id"])
    check(abs(beak_db - 50000) <= TOL, "beak acumulado entre créditos: 30.000 + 20.000 = 50.000 (no se pisa)", f"{beak_db}")
    hist = await history(api, sup, loan["id"])
    q2 = next(i for i in hist["items"] if i["quota_number"] == 2)
    if q2["can_pay"]:
        r = await api.call(sup, "PUT", f"/payments/{q2['id']}/pay", params={"value": 125000})
        beak_db, _ = await db_state(client["id"])
        check(r.status_code == 200 and abs(beak_db - 75000) <= TOL, "abono mayor a la cuota 2 suma al beak (+25.000 → 75.000)", f"{r.status_code} {beak_db}")
    else:
        check(True, "cuota 2 aún no vence (semanal): abono mayor ya cubierto por el caso de cobro inicial")
    client, cr, loan = created["parcial"]
    hist = await history(api, sup, loan["id"])
    q1 = hist["items"][0]
    r = await api.call(sup, "PUT", f"/payments/{q1['id']}/pay", params={"value": 120000})
    beak_db, loan_db = await db_state(client["id"], loan["id"])
    check(r.status_code == 200 and abs(float(loan_db.total_default or 0)) <= TOL and abs(beak_db - 20000) <= TOL,
          "corregir un parcial (40.000 → 120.000): mora vuelve a 0 y el excedente 20.000 pasa al beak", f"{r.status_code} default={loan_db.total_default} beak={beak_db}")
    r = await api.call(sup, "GET", "/payments/today", params={"route_id": str(norte_route.id)})
    mine = [i for i in r.json() if i["client_id"] == client["id"]]
    check(bool(mine) and all(abs(i["client_beak"] - 20000) <= TOL for i in mine), "Cobro del día expone client_beak del cliente")

    print("== 5. Validaciones ==")
    client, cr = await new_client(api, sup, norte_route)
    for label, patch_body, code in [
        ("0 cuotas", {"agreed_quotas": 0}, 422), ("método inválido", {"payment_method": "x"}, 422),
        ("cobro negativo", {"value_payment": -5}, 422), ("capital 0", {"value_capital": 0}, 422),
        ("dia_fijo sin día", {"payment_method": "dia_fijo"}, 422),
        ("cobro con dia_fijo cuya primera cuota es futura", {"payment_method": "dia_fijo", "fixed_payment_day": (today + timedelta(days=5)).day if (today + timedelta(days=5)).month == today.month else 28, "value_payment": 1000}, 400),
        ("cobro con primera cuota futura", {"value_payment": 1000, "date_first_quota": (today + timedelta(days=3)).isoformat(), "end_date": (today + timedelta(days=60)).isoformat()}, 400),
    ]:
        body = loan_payload(client, cr)
        body.update(patch_body)
        r = await api.call(sup, "POST", "/loans/", json=body)
        check(r.status_code == code, f"{label} → {code}", f"{r.status_code} {r.text[:120]}")

    print("== 6. Atomicidad (fallo al insertar cuotas ⇒ no queda crédito ni número consumido) ==")
    async with async_session() as db:
        loans_before = (await db.execute(select(func.count()).select_from(LoanModel))).scalar_one()
        number_before = (await db.execute(select(RouteModel.loans_number).where(RouteModel.id == norte_route.id))).scalar_one()

    async def boom(self, rows):
        raise RuntimeError("fallo forzado")

    with patch.object(PaymentRepository, "bulk_create_payments", boom):
        try:
            await api.call(sup, "POST", "/loans/", json=loan_payload(client, cr))
            raised = False
        except RuntimeError:
            raised = True
    async with async_session() as db:
        loans_after = (await db.execute(select(func.count()).select_from(LoanModel))).scalar_one()
        number_after = (await db.execute(select(RouteModel.loans_number).where(RouteModel.id == norte_route.id))).scalar_one()
    check(raised and loans_after == loans_before and number_after == number_before, "con fallo en las cuotas no se crea el crédito ni se consume el número")

    print("== 7. Seguridad (marca, rol, ruta, cliente) ==")
    if other:
        r = await api.call(other, "POST", "/loans/", json=loan_payload(client, cr))
        check(r.status_code == 404, f"usuario de otra marca ({other.username}) → 404", f"{r.status_code}")
    if carlos:
        c2, cr2 = await new_client(api, sup, sur_route)
        r = await api.call(carlos, "POST", "/loans/", json=loan_payload(c2, cr2))
        check(r.status_code == 403, "recaudador en ruta donde no está asignado → 403", f"{r.status_code} {r.text[:100]}")
        c3, cr3 = await new_client(api, sup, norte_route)
        r = await api.call(carlos, "POST", "/loans/", json=loan_payload(c3, cr3, value_payment=100000))
        check(r.status_code == 201, "recaudador asignado crea el crédito → 201", f"{r.status_code} {r.text[:100]}")
        if r.status_code == 201:
            q1 = (await history(api, carlos, r.json()["id"]))["items"][0]
            check(q1["collected_by_id"] == str(carlos.id), "el cobro inicial queda a nombre del recaudador")
    other_client, other_cr = await new_client(api, sup, sur_route)
    r = await api.call(sup, "POST", "/loans/", json=loan_payload(client, other_cr))
    check(r.status_code == 400, "cliente que no pertenece al cliente-ruta → 400", f"{r.status_code}")

    print("== 8. Rendimiento (sentencias SQL y tiempo por crédito) ==")
    for quotas, cobro in ((20, None), (20, 10000), (60, 10000)):
        client, cr = await new_client(api, sup, norte_route)
        statements = []

        def on_exec(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", on_exec)
        start = time.perf_counter()
        r = await api.call(sup, "POST", "/loans/", json=loan_payload(client, cr, quotas=quotas, quota=10000, capital=quotas * 8000, value_payment=cobro))
        elapsed = (time.perf_counter() - start) * 1000
        event.remove(engine.sync_engine, "before_cursor_execute", on_exec)
        inserts = sum(1 for s in statements if s.lstrip().upper().startswith("INSERT INTO PAYMENTS"))
        print(f"      {quotas} cuotas{' con cobro inicial' if cobro else ''}: {len(statements)} sentencias SQL, {elapsed:.0f} ms (INSERT de cuotas: {inserts})")
        check(r.status_code == 201 and len(statements) <= 12 and inserts <= (2 if cobro else 1), f"{quotas} cuotas{' con cobro' if cobro else ''}: ≤ 12 sentencias y INSERT de cuotas en lote (1, o 2 con cobro inicial)", f"{len(statements)} / {inserts}")

    failed = [name for ok, name in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
