#!/usr/bin/env python3
"""
QA del historial de cuotas (`GET /payments/history`) y del abono con recaudador (`PUT /payments/{id}/pay`).

Compara la API contra un cálculo independiente en Python puro sobre las filas crudas de `payments`
(sin SQL de estados) para todos los créditos demo de la marca NORTE01, prueba filtros, paginación y
seguridad por marca y, con `--mutate`, opera datos reales (abono parcial y luego total) verificando
saldo, estado y `collected_by`. NO borra nada: los abonos de prueba se conservan.

Uso (desde el contenedor api):  python scripts/qa_payment_history.py [--mutate]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.loan_model import LoanModel  # noqa: E402
from app.infrastructure.models.payment_model import PaymentModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_reports import RESULTS, TOL, Api, check, diff  # noqa: E402


def expected_item(p: PaymentModel, today: date, names: dict) -> dict:
    """Cálculo independiente de una cuota (definiciones del docstring de payment_history_repository)."""
    value, applied = float(p.value or 0), float(p.applied or 0)
    paid = applied >= value - 0.01
    overdue = (not paid) and p.pay_date < today
    return {
        "id": str(p.id), "quota_number": p.quota_number, "pay_date": p.pay_date.isoformat(),
        "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        "value": value, "applied": applied, "balance": max(value - applied, 0.0),
        "status": "pagado" if paid else ("mora" if overdue else "pendiente"),
        "days_overdue": (today - p.pay_date).days if overdue else 0,
        "paid_late_days": max((p.payment_date - p.pay_date).days, 0) if paid and p.payment_date else 0,
        "collected_by_id": str(p.collected_by) if p.collected_by else None,
        "collected_by_name": names.get(p.collected_by),
        "can_pay": (not paid) and p.pay_date <= today,
    }


async def expected_for(db, loan_id, today: date) -> tuple[list[dict], dict]:
    rows = (await db.execute(
        select(PaymentModel).where(PaymentModel.loan_id == loan_id, PaymentModel.active.is_(True)).order_by(PaymentModel.quota_number)
    )).scalars().all()
    names = {u.id: u.full_name for u in (await db.execute(select(UserModel))).scalars().all()}
    items = [expected_item(p, today, names) for p in rows]
    due = sum(i["value"] for i in items)
    paid = sum(i["applied"] for i in items)
    summary = {
        "total_quotas": len(items),
        "paid": sum(i["status"] == "pagado" for i in items),
        "pending": sum(i["status"] == "pendiente" for i in items),
        "overdue": sum(i["status"] == "mora" for i in items),
        "total_due": due, "total_paid": paid, "total_balance": sum(i["balance"] for i in items),
        "paid_percent": round(min(100.0, paid / due * 100), 1) if due else 0.0,
    }
    return items, summary


async def main(mutate: bool) -> int:
    api = Api()
    today = today_bogota()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        sup = users["super_norte"]
        other = next((u for u in users.values() if u.brand_id and u.brand_id != norte.id and u.type_user.value != "01"), None)
        loans = (await db.execute(
            select(LoanModel).where(LoanModel.loan_number.between(2001, 2012)).order_by(LoanModel.loan_number)
        )).scalars().all()

    print("== 1. Historial por crédito vs cálculo independiente ==")
    for loan in loans:
        async with async_session() as db:
            exp_items, exp_summary = await expected_for(db, loan.id, today)
        r = await api.call(sup, "GET", "/payments/history", params={"loan_id": str(loan.id), "page_size": 100})
        ok = r.status_code == 200
        body = r.json() if ok else {}
        problems = diff({"items": exp_items, "summary": exp_summary}, {"items": body.get("items", []), "summary": body.get("summary", {})}) if ok else [r.text[:150]]
        check(ok and not problems, f"crédito {loan.loan_number}: {len(exp_items)} cuotas y resumen == cálculo independiente", "; ".join(problems[:4]))

    print("== 2. Filtros y paginación (crédito con mora) ==")
    loan = next(l for l in loans if l.loan_number == 2009)
    async with async_session() as db:
        exp_items, exp_summary = await expected_for(db, loan.id, today)
    for status in ("pagado", "pendiente", "mora"):
        r = await api.call(sup, "GET", "/payments/history", params={"loan_id": str(loan.id), "status": status, "page_size": 100})
        ids = [i["id"] for i in r.json()["items"]]
        check(ids == [i["id"] for i in exp_items if i["status"] == status], f"filtro status={status} devuelve solo esas cuotas")
    seen, page = [], 1
    while True:
        r = await api.call(sup, "GET", "/payments/history", params={"loan_id": str(loan.id), "page": page, "page_size": 7})
        body = r.json()
        seen += [i["id"] for i in body["items"]]
        if page >= body["pages"]:
            break
        page += 1
    check(seen == [i["id"] for i in exp_items], "paginación de 7 en 7 recorre todas las cuotas sin solapes y en orden")
    r = await api.call(sup, "GET", "/payments/history", params={"loan_id": str(loan.id), "page_size": 5})
    check(r.json()["summary"]["total_quotas"] == exp_summary["total_quotas"], "el resumen cubre todas las cuotas, no solo la página")

    print("== 3. Validaciones y seguridad ==")
    check((await api.call(sup, "GET", "/payments/history", params={"loan_id": str(loan.id), "status": "x"})).status_code == 422, "status inválido → 422")
    check((await api.call(sup, "GET", "/payments/history")).status_code == 422, "sin loan_id → 422")
    check((await api.call(sup, "GET", "/payments/history", params={"loan_id": "00000000-0000-0000-0000-000000000000"})).status_code == 404, "crédito inexistente → 404")
    if other:
        check((await api.call(other, "GET", "/payments/history", params={"loan_id": str(loan.id)})).status_code == 404, f"usuario de otra marca ({other.username}) no ve el crédito → 404")

    if mutate:
        await mutations(api, sup, today)

    failed = [name for ok, name in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN: {failed}" if failed else ""))
    return 1 if failed else 0


async def mutations(api: Api, sup: UserModel, today: date) -> None:
    print("== 4. Abonos en vivo (se conservan) ==")
    async with async_session() as db:
        due = (await db.execute(
            select(PaymentModel).join(LoanModel, LoanModel.id == PaymentModel.loan_id)
            .where(LoanModel.loan_number.between(2001, 2012), LoanModel.active.is_(True),
                   PaymentModel.pay_date <= today, func.coalesce(PaymentModel.applied, 0) == 0)
            .order_by(PaymentModel.pay_date.desc(), PaymentModel.quota_number)
        )).scalars().first()
        future = (await db.execute(
            select(PaymentModel).join(LoanModel, LoanModel.id == PaymentModel.loan_id)
            .where(LoanModel.loan_number.between(2001, 2012), PaymentModel.pay_date > today, func.coalesce(PaymentModel.applied, 0) == 0)
        )).scalars().first()
        value = float(due.value)
        loan_id = due.loan_id

    async def row(payment_id):
        r = await api.call(sup, "GET", "/payments/history", params={"loan_id": str(loan_id), "page_size": 100})
        return next(i for i in r.json()["items"] if i["id"] == str(payment_id)), r.json()["summary"]

    before, sum_before = await row(due.id)
    check(before["can_pay"] and before["status"] in ("mora", "pendiente"), "la cuota elegida está impaga y se puede abonar")
    partial = round(value / 2, 2)
    r = await api.call(sup, "PUT", f"/payments/{due.id}/pay", params={"value": partial})
    check(r.status_code == 200, "abono parcial 200", r.text[:150])
    mid, sum_mid = await row(due.id)
    check(abs(mid["applied"] - partial) <= TOL and abs(mid["balance"] - (value - partial)) <= TOL, f"abono parcial de ${partial:,.0f}: aplicado y saldo exactos")
    check(mid["collected_by_id"] == str(sup.id), "se guardó quién recaudó (collected_by = usuario autenticado)")
    check(abs(sum_mid["total_paid"] - sum_before["total_paid"] - partial) <= TOL, "el resumen del crédito sube exactamente el abono")
    r = await api.call(sup, "PUT", f"/payments/{due.id}/pay", params={"value": value})
    check(r.status_code == 200, "abono total (acumulado) 200", r.text[:150])
    end, sum_end = await row(due.id)
    check(end["status"] == "pagado" and end["balance"] <= TOL and not end["can_pay"], "cuota pagada: estado pagado, saldo 0 y sin opción de abonar")
    check(abs(sum_end["total_paid"] - sum_before["total_paid"] - value) <= TOL and sum_end["paid"] == sum_before["paid"] + 1, "resumen: +1 cuota pagada y pagado sube el valor de la cuota")
    r = await api.call(sup, "PUT", f"/payments/{due.id}/pay", params={"value": value})
    check(r.status_code == 400, "abonar una cuota ya pagada → 400", r.text[:150])
    if future:
        r = await api.call(sup, "PUT", f"/payments/{future.id}/pay", params={"value": float(future.value)})
        check(r.status_code == 400, "abonar una cuota futura → 400", r.text[:150])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QA del historial de cuotas (no borra datos)")
    parser.add_argument("--mutate", action="store_true", help="Abona una cuota real (parcial y total) y verifica")
    sys.exit(asyncio.run(main(parser.parse_args().mutate)))
