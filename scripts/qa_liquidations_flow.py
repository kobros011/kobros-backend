#!/usr/bin/env python3
"""
QA del flujo completo de una liquidación, de punta a punta y con dos usuarios reales:

  1. El COBRADOR (qd_carlos, ruta asignada) cobra cuotas (hoy, atrasada, parcial, excedente) y registra gastos.
  2. Un ADMIN asignado a la misma ruta (admin_norte) hace la vista previa, cierra la caja a nombre del cobrador,
     confirma, y REABRE el cierre.
  Se ejecuta DOS veces: A) el cobrador además entrega créditos nuevos; B) sin créditos nuevos.

Verifica que cada pago y gasto liquidado guarda `liquidated`, `date_liquidated`, `liquidation_id` y `liquidated_by`,
que se escribe con UPDATE en lote (una sentencia por tabla, no pago por pago), que reabrir lo deja todo limpio y que las
cifras coinciden con un cálculo independiente sobre las filas crudas. No borra nada (datos QD-).

Uso (contenedor api):  python scripts/qa_liquidations_flow.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from uuid import UUID

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import event, select, text  # noqa: E402

from app.core.clock import today_bogota
from app.infrastructure.dababase.db import async_session, engine
from app.infrastructure.models.brand_model import BrandModel
from app.infrastructure.models.expense_model import ExpenseConceptModel
from app.infrastructure.models.user_model import UserModel
from scripts.qa_liquidations import STAMP, TOL, new_loan, new_route, pay, quota, raw_oracle, same
from scripts.qa_reports import RESULTS, Api, check

COUNTER = {"n": 0}


async def marks(table: str, route_id: UUID, who: UUID | None, day):
    """Filas crudas de pagos/gastos del cobrador ese día con sus marcas de liquidación."""
    async with async_session() as db:
        if table == "payments":
            sql = """SELECT p.id, p.liquidated, p.date_liquidated, p.liquidation_id, p.liquidated_by, p.collected_by
                     FROM payments p JOIN loans l ON l.id = p.loan_id JOIN clientsroutes cr ON cr.id = l.clientroute_id
                     WHERE cr.route_id = :r AND p.collected_by = :w AND p.payment_date = :d AND COALESCE(p.applied, 0) > 0"""
        else:
            sql = "SELECT id, liquidated, date_liquidated, liquidation_id, liquidated_by FROM expenses WHERE route_id = :r AND created_by = :w AND date = :d"
        return (await db.execute(text(sql), {"r": route_id, "w": who, "d": day})).mappings().all()


async def scenario(api: Api, name: str, with_new_loans: bool, users: dict, norte, concept) -> None:
    today = today_bogota()
    sup, carlos, admin = users["super_norte"], users["qd_carlos"], users.get("admin_norte") or users["super_norte"]
    print(f"\n==== Escenario {name}: {'CON' if with_new_loans else 'SIN'} créditos nuevos ====")
    route = await new_route([carlos.id, admin.id], norte.id, f"F{name}")

    # --- preparación: créditos existentes (los crea el super, no cuentan como créditos nuevos del cobrador)
    due = await new_loan(api, sup, route, first_offset=0)            # cuota de hoy
    late = await new_loan(api, sup, route, first_offset=-4)          # cuotas atrasadas
    part = await new_loan(api, sup, route, first_offset=0)           # abono parcial
    over = await new_loan(api, sup, route, first_offset=0)           # pago de más
    for _ in range(6):                                               # varios cobros más: el cierre los marca en lote
        await new_loan(api, sup, route, first_offset=0)

    # --- 1) el COBRADOR cobra
    print("-- 1. Cobros del cobrador")
    await pay(api, carlos, due["id"], 1, 100000)
    await pay(api, carlos, late["id"], 1, 100000)
    await pay(api, carlos, part["id"], 1, 40000)
    await pay(api, carlos, over["id"], 1, 130000)
    async with async_session() as db:
        extra_ids = (await db.execute(text("""
            SELECT p.id FROM payments p JOIN loans l ON l.id = p.loan_id JOIN clientsroutes cr ON cr.id = l.clientroute_id
            WHERE cr.route_id = :r AND p.quota_number = 1 AND p.applied IS NULL AND p.pay_date = :d"""), {"r": route.id, "d": today})).scalars().all()
    for pid in extra_ids:
        r = await api.call(carlos, "PUT", f"/payments/{pid}/pay", params={"value": 100000})
        assert r.status_code == 200, r.text
    expected_receipts = 4 + len(extra_ids)
    check(len(extra_ids) == 6, f"{name}: el cobrador registra {expected_receipts} cobros (cuota de hoy, atrasada, parcial, excedente y 6 más)")

    # --- 2) el COBRADOR registra gastos
    print("-- 2. Gastos del cobrador")
    for label, value in (("Combustible moto", 25000), ("Almuerzo en ruta", 18000)):
        r = await api.call(carlos, "POST", "/expenses/", json={"date": today.isoformat(), "value": value, "name": f"QA {name} {label}",
                                                              "expensesconcept_id": str(concept.id), "route_id": str(route.id)})
        check(r.status_code == 201, f"{name}: el cobrador registra el gasto '{label}' (201)", r.text[:120])

    # --- 3) créditos nuevos entregados por el cobrador (solo escenario A)
    new_loans_total = 0
    if with_new_loans:
        print("-- 3. Créditos nuevos del cobrador")
        for capital in (300000, 200000):
            COUNTER["n"] += 1
            tag = f"{STAMP}{name}{COUNTER['n']:02d}"
            rc = await api.call(sup, "POST", "/clients/", json={
                "full_name": f"QD Flow {tag}", "id_document": f"QD-F{tag}", "current_address": "Calle QA", "current_phone": "3000000000",
                "current_mobile": "3000000000", "neighborhood": "QA", "linking_date": datetime.now().isoformat(),
                "routes_ids": [str(route.id)], "brand_id": str(sup.brand_id)})
            client = rc.json()
            crs = (await api.call(sup, "GET", "/clientroute/", params={"route_id": str(route.id)})).json()
            cr = next(c for c in crs if c["client_id"] == client["id"])
            r = await api.call(carlos, "POST", "/loans/", json={
                "end_date": (today + timedelta(days=10)).isoformat(), "value_quota_fixed": 60000, "agreed_quotas": 5,
                "date_first_quota": (today + timedelta(days=1)).isoformat(), "payment_method": "diaria", "value_capital": capital,
                "current_address": "Calle QA", "current_mobile": "3000000000", "clientroute_id": cr["id"], "client_id": client["id"]})
            check(r.status_code == 201, f"{name}: el cobrador entrega un crédito de ${capital:,.0f} (201)", r.text[:120])
            new_loans_total += capital

    # --- 4) el ADMIN revisa la vista previa (consolidada y del cobrador)
    print("-- 4. Vista previa del admin")
    r = await api.call(admin, "GET", "/liquidations/preview", params={"route_id": str(route.id), "date": today.isoformat(), "collector_id": str(carlos.id)})
    preview = r.json()
    oracle = await raw_oracle(route.id, today, carlos.id)
    problems = same(preview, oracle)
    check(r.status_code == 200 and not problems, f"{name}: la vista previa del admin (cobrador) == cálculo independiente", "; ".join(problems[:4]))
    check(abs(preview["collected_total"] - (100000 + 100000 + 40000 + 130000 + 6 * 100000)) <= TOL, f"{name}: recaudo = $1.070.000", str(preview["collected_total"]))
    check(abs(preview["expenses_total"] - 43000) <= TOL, f"{name}: gastos del cobrador = $43.000", str(preview["expenses_total"]))
    check(abs(preview["new_loans_total"] - new_loans_total) <= TOL and preview["new_loans_count"] == (2 if with_new_loans else 0),
          f"{name}: créditos nuevos = ${new_loans_total:,.0f} ({2 if with_new_loans else 0})", str(preview["new_loans_total"]))
    check(abs(preview["beak_generated"] - 30000) <= TOL and preview["partial_count"] == 1, f"{name}: excedente a favor $30.000 y 1 abono parcial")
    check(len(preview["new_loans"]) == (2 if with_new_loans else 0), f"{name}: la lista de créditos nuevos del cierre tiene {2 if with_new_loans else 0} filas")
    consolidated = (await api.call(admin, "GET", "/liquidations/preview", params={"route_id": str(route.id), "date": today.isoformat()})).json()
    check(not same(consolidated, await raw_oracle(route.id, today, None)), f"{name}: la vista previa consolidada de la ruta == cálculo independiente")

    # --- 5) el ADMIN cierra la caja (medimos las sentencias)
    print("-- 5. Cierre de caja por el admin")
    base = 500000
    expected = base + preview["collected_total"] - preview["expenses_total"] - preview["new_loans_total"]
    statements: list[str] = []

    def on_exec(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", on_exec)
    r = await api.call(admin, "POST", "/liquidations/", json={
        "route_id": str(route.id), "date": today.isoformat(), "value_base_delivered": base, "cash_delivered": expected - 5000,
        "note": "faltan $5.000 por vuelto", "collector_id": str(carlos.id)})
    event.remove(engine.sync_engine, "before_cursor_execute", on_exec)
    check(r.status_code == 201, f"{name}: el admin cierra la caja a nombre del cobrador (201)", r.text[:160])
    liq = r.json()
    check(abs(liq["expected_cash"] - expected) <= TOL and abs(liq["difference"] + 5000) <= TOL and liq["status"] == "pendiente",
          f"{name}: esperado ${expected:,.0f}, diferencia −$5.000 (faltante) y estado pendiente", str(liq["difference"]))
    check(liq["receipts_count"] == expected_receipts and liq["new_loans_count"] == (2 if with_new_loans else 0), f"{name}: el cierre guarda {expected_receipts} recibos y sus créditos nuevos")
    updates = [s for s in statements if s.lstrip().upper().startswith("UPDATE")]
    pay_up = [s for s in updates if "UPDATE payments" in s]
    exp_up = [s for s in updates if "UPDATE expenses" in s]
    print(f"      sentencias del cierre: {len(statements)} (UPDATE payments: {len(pay_up)}, UPDATE expenses: {len(exp_up)}) para {expected_receipts} pagos y 2 gastos")
    check(len(pay_up) == 1 and len(exp_up) == 1, f"{name}: los {expected_receipts} pagos y 2 gastos se marcan con UN UPDATE por tabla (en lote), no uno por uno",
          f"{len(pay_up)}/{len(exp_up)}")

    # --- 6) cada pago y gasto guarda si fue liquidado, cuándo y quién
    print("-- 6. Marcas guardadas")
    prow = await marks("payments", route.id, carlos.id, today)
    erow = await marks("expenses", route.id, carlos.id, today)
    ok_p = len(prow) == expected_receipts and all(r["liquidated"] and r["date_liquidated"] == today and r["liquidated_by"] == admin.id and str(r["liquidation_id"]) == liq["id"] for r in prow)
    ok_e = len(erow) == 2 and all(r["liquidated"] and r["date_liquidated"] == today and r["liquidated_by"] == admin.id and str(r["liquidation_id"]) == liq["id"] for r in erow)
    check(ok_p, f"{name}: los {expected_receipts} pagos quedan liquidated=true, fecha de hoy (Colombia), liquidated_by=admin y liquidation_id del cierre")
    check(ok_e, f"{name}: los 2 gastos quedan con las mismas marcas")
    today_list = (await api.call(carlos, "GET", "/payments/today", params={"route_id": str(route.id)})).json()
    check(not any(i["id"] in {str(r["id"]) for r in prow} for i in today_list), f"{name}: los pagos liquidados ya no aparecen en Cobro del día")
    again = await api.call(admin, "POST", "/liquidations/", json={"route_id": str(route.id), "date": today.isoformat(), "value_base_delivered": base, "cash_delivered": 1, "collector_id": str(carlos.id)})
    check(again.status_code == 409, f"{name}: un segundo cierre del mismo cobrador y día → 409")

    # --- 7) el ADMIN confirma; el cobrador no puede reabrir
    print("-- 7. Confirmar y reabrir")
    check((await api.call(carlos, "POST", f"/liquidations/{liq['id']}/confirm")).status_code == 403, f"{name}: el cobrador no puede confirmar → 403")
    r = await api.call(admin, "POST", f"/liquidations/{liq['id']}/confirm")
    check(r.status_code == 200 and r.json()["status"] == "confirmada", f"{name}: el admin confirma el cierre", r.text[:120])
    check((await api.call(carlos, "POST", f"/liquidations/{liq['id']}/reopen")).status_code == 403, f"{name}: el cobrador no puede reabrir → 403")
    detail = (await api.call(admin, "GET", f"/liquidations/{liq['id']}")).json()
    check(len(detail["payments"]) == expected_receipts and len(detail["expenses"]) == 2 and len(detail["new_loans"]) == (2 if with_new_loans else 0) and not detail["outdated"],
          f"{name}: el detalle lista {expected_receipts} recibos, 2 gastos y {2 if with_new_loans else 0} créditos nuevos, sin desactualización")

    # --- 8) REABRIR: todo vuelve a quedar sin liquidar y se puede volver a cerrar
    statements.clear()
    event.listen(engine.sync_engine, "before_cursor_execute", on_exec)
    r = await api.call(admin, "POST", f"/liquidations/{liq['id']}/reopen")
    event.remove(engine.sync_engine, "before_cursor_execute", on_exec)
    check(r.status_code == 200 and r.json()["status"] == "reabierta", f"{name}: el admin reabre el cierre confirmado", r.text[:120])
    reopen_up = [s for s in statements if s.lstrip().upper().startswith("UPDATE") and ("UPDATE payments" in s or "UPDATE expenses" in s)]
    check(len(reopen_up) == 2, f"{name}: reabrir libera pagos y gastos con 2 UPDATE en lote", str(len(reopen_up)))
    prow = await marks("payments", route.id, carlos.id, today)
    erow = await marks("expenses", route.id, carlos.id, today)
    clean = lambda rows: all(not r["liquidated"] and r["date_liquidated"] is None and r["liquidation_id"] is None and r["liquidated_by"] is None for r in rows)  # noqa: E731
    check(len(prow) == expected_receipts and clean(prow) and len(erow) == 2 and clean(erow), f"{name}: tras reabrir, pagos y gastos quedan sin liquidar (fecha, cierre y responsable vacíos)")
    after = (await api.call(admin, "GET", "/liquidations/preview", params={"route_id": str(route.id), "date": today.isoformat(), "collector_id": str(carlos.id)})).json()
    check(not same(after, oracle) and after["existing_liquidation_id"] is None, f"{name}: la vista previa vuelve a las mismas cifras y sin cierre vigente")
    r = await api.call(admin, "POST", "/liquidations/", json={"route_id": str(route.id), "date": today.isoformat(), "value_base_delivered": base, "cash_delivered": expected, "collector_id": str(carlos.id)})
    check(r.status_code == 201 and abs(r.json()["difference"]) <= TOL, f"{name}: se vuelve a cerrar tras reabrir y ahora cuadra (diferencia 0)", r.text[:120])
    r2 = await api.call(admin, "POST", f"/liquidations/{r.json()['id']}/confirm")
    check(r2.status_code == 200, f"{name}: el nuevo cierre se confirma")
    hist = (await api.call(admin, "GET", "/liquidations/", params={"route_id": str(route.id)})).json()
    check(hist["summary"]["count"] >= 1 and any(i["status"] == "confirmada" for i in hist["items"]), f"{name}: el historial muestra el cierre confirmado y totales del filtro")


async def main() -> int:
    api = Api()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        concept = (await db.execute(select(ExpenseConceptModel).where(ExpenseConceptModel.concept == "Combustible", ExpenseConceptModel.brand_id == norte.id))).scalars().first()
    await scenario(api, "A", True, users, norte, concept)
    await scenario(api, "B", False, users, norte, concept)

    failed = [name for ok, name in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
