#!/usr/bin/env python3
"""
QA de Reportes: compara la API contra el oráculo independiente (`report_oracle.py`) y contra SQL crudo,
prueba seguridad/bordes y, con `--mutate`, opera datos reales (pago, gasto, cliente+crédito, cliente
inactivo) verificando que los reportes se muevan exactamente por el valor operado. NO borra nada.

Uso (desde el contenedor api):  python scripts/qa_reports.py [--mutate]
Requiere haber corrido antes scripts/seed_dashboard_demo.py.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402

from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session, engine  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.loan_model import LoanModel  # noqa: E402
from app.infrastructure.models.payment_model import PaymentModel  # noqa: E402
from app.infrastructure.models.route_model import RouteModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from app.infrastructure.models.expense_model import ExpenseConceptModel  # noqa: E402
from app.infrastructure.utils.require_authentication import get_current_user, require_authentication  # noqa: E402
from app.main import app  # noqa: E402
from scripts.report_oracle import compute_critical, compute_period, compute_summary, load_raw, scope_of  # noqa: E402

engine.echo = False
logging.disable(logging.CRITICAL)

TOL = 0.011
RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    RESULTS.append((ok, name))
    print(("OK    " if ok else "FALLA ") + name + (f"  → {detail}" if detail and not ok else ""))
    return ok


def norm(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if isinstance(value, dict):
        return {k: norm(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [norm(v) for v in value]
    return value


def diff(a, b, path="") -> list[str]:
    """Diferencias entre dos estructuras (floats con tolerancia de 1 centavo)."""
    a, b = norm(a), norm(b)
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                out.append(f"{path}.{key}: falta en {'oráculo' if key not in a else 'API'}")
            else:
                out += diff(a[key], b[key], f"{path}.{key}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: longitud {len(a)} (oráculo) vs {len(b)} (API)"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f"{path}[{i}]")]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return [] if abs(a - b) <= TOL else [f"{path}: {a} (oráculo) vs {b} (API)"]
    return [] if a == b else [f"{path}: {a!r} (oráculo) vs {b!r} (API)"]


class Api:
    def __init__(self):
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://qa")

    async def call(self, user: UserModel, method: str, path: str, **kwargs):
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[require_authentication] = lambda: user
        return await self.client.request(method, path, **kwargs)


async def sql_headlines(db, brand_id, today):
    """Cifras clave con SQL crudo escrito aparte de `loan_stats` (tercera fuente independiente)."""
    row = (await db.execute(text("""
        WITH paid AS (SELECT loan_id, COALESCE(SUM(applied),0) AS paid FROM payments GROUP BY loan_id),
        due AS (SELECT loan_id, SUM(value - COALESCE(applied,0)) AS due
                FROM payments WHERE pay_date < :today AND value - COALESCE(applied,0) > 0.01 GROUP BY loan_id),
        base AS (
          SELECT l.id, l.value_total_loan AS total, COALESCE(p.paid,0) AS paid,
                 l.value_total_loan - COALESCE(p.paid,0) AS balance, COALESCE(d.due,0) AS due
          FROM loans l
          JOIN clientsroutes cr ON cr.id = l.clientroute_id
          JOIN routes r ON r.id = cr.route_id AND r.active
          LEFT JOIN paid p ON p.loan_id = l.id
          LEFT JOIN due d ON d.loan_id = l.id
          WHERE l.active AND (CAST(:brand AS uuid) IS NULL OR r.brand_id = CAST(:brand AS uuid)))
        SELECT COALESCE(SUM(balance) FILTER (WHERE balance > 0),0),
               COALESCE(SUM(LEAST(due, balance)) FILTER (WHERE LEAST(due, balance) > 0),0),
               COALESCE(SUM(paid) FILTER (WHERE balance > 0),0),
               COALESCE(SUM(total) FILTER (WHERE balance > 0),0),
               COUNT(*) FILTER (WHERE balance > 0),
               COUNT(*) FILTER (WHERE LEAST(due, balance) > 0)
        FROM base
    """), {"today": today, "brand": brand_id})).one()
    return {"portfolio_total": float(row[0]), "delinquency_total": float(row[1]), "total_paid": float(row[2]), "total_lent": float(row[3]),
            "portfolio_loans": row[4], "delinquency_loans": row[5]}


async def main(mutate: bool) -> int:
    api = Api()
    today = today_bogota()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        routes = {r.name: r for r in (await db.execute(select(RouteModel).where(RouteModel.brand_id == norte.id))).scalars().all()}
        missing = [n for n in ("Ruta Norte", "Ruta Centro", "Ruta Sur") if n not in routes]
        if missing or "qd_laura" not in users:
            print("Faltan datos demo; ejecuta scripts/seed_dashboard_demo.py")
            return 1
        sup, dev, partner = users["super_norte"], users["admin_david"], users["qd_laura"]
        raw = await load_raw(db)
        sql = await sql_headlines(db, norte.id, today)

    print("== 1. Resumen (super_norte) vs oráculo ==")
    base_scope = scope_of(raw, brand_id=norte.id, partner_id=None, route_id=None, collector_id=None)
    r = await api.call(sup, "GET", "/reports/dashboard/summary")
    check(r.status_code == 200, "GET /summary 200", r.text[:200])
    summary = r.json()
    expected = compute_summary(raw, base_scope, today, 90)
    problems = diff(expected, {k: v for k, v in summary.items() if k != "critical_days"})
    check(not problems, "summary == oráculo (KPIs, diario, composición, por ruta, por recaudador)", "; ".join(problems[:6]))
    k = summary["kpis"]
    check(abs(k["portfolio_total"] - sql["portfolio_total"]) <= TOL and abs(k["delinquency_total"] - sql["delinquency_total"]) <= TOL
          and abs(k["total_paid"] - sql["total_paid"]) <= TOL and abs(k["total_lent"] - sql["total_lent"]) <= TOL
          and k["portfolio_loans"] == sql["portfolio_loans"] and k["delinquency_loans"] == sql["delinquency_loans"],
          "KPIs clave == SQL crudo (cartera, mora, pagado, colocado, conteos)", f"{k} vs {sql}")
    comp = summary["composition"]
    check(abs(comp["up_to_date"] + comp["mild"] + comp["critical"] - k["portfolio_total"]) <= TOL, "composición suma la cartera total")
    check(abs(summary["composition"]["mild"] + summary["composition"]["critical"] - k["delinquency_total"]) <= TOL, "mora leve + crítica == KPI de mora")

    print("== 2. Consistencia con Cartera y mora crítica ==")
    pf = (await api.call(sup, "GET", "/reports/portfolio")).json()
    dl = (await api.call(sup, "GET", "/reports/delinquency")).json()
    ps = (await api.call(sup, "GET", "/reports/portfolio/summary")).json()
    ds = (await api.call(sup, "GET", "/reports/delinquency/summary")).json()
    check(abs(sum(i["balance"] for i in pf) - k["portfolio_total"]) <= TOL and len(pf) == k["portfolio_loans"], "Σ /portfolio == KPI cartera")
    check(abs(sum(i["balance"] for i in dl) - k["delinquency_total"]) <= TOL and len(dl) == k["delinquency_loans"], "Σ /delinquency == KPI mora")
    check(abs(ps["total_balance"] - k["portfolio_total"]) <= TOL and abs(ds["total_balance"] - k["delinquency_total"]) <= TOL, "summaries de Cartera == KPIs")
    check(all(i["total_paid"] > 0 for i in pf if i["loan_number"] in (2001, 2004)), "total_paid ya no es 0 (bug de 'PAGADO' corregido)")

    full = compute_critical(raw, base_scope, today)
    pages, page = [], 1
    while True:
        r = await api.call(sup, "GET", "/reports/dashboard/critical", params={"page": page})
        body = r.json()
        pages.append(body)
        if page >= body["pages"]:
            break
        page += 1
    flat = [item for p in pages for item in p["items"]]
    check(pages[0]["page_size"] == 5 and all(len(p["items"]) <= 5 for p in pages), "critical pagina de a 5")
    check(pages[0]["total"] == len(full) == k["delinquency_loans"], "critical.total == créditos en mora")
    problems = diff([{k2: v for k2, v in i.items() if k2 != "collector_names"} for i in full], [{k2: v for k2, v in i.items() if k2 != "collector_names"} for i in flat])
    check(not problems, "critical (todas las páginas) == oráculo, sin solapes y en orden", "; ".join(problems[:5]))
    check(len({i["loan_id"] for i in flat}) == len(flat), "critical sin duplicados entre páginas")
    r = await api.call(sup, "GET", "/reports/dashboard/critical", params={"text": "Natalia"})
    check(r.json()["total"] == len(compute_critical(raw, base_scope, today, "Natalia")) >= 1, "critical?text= filtra por nombre")
    r = await api.call(sup, "GET", "/reports/dashboard/critical", params={"text": "2003"})
    check(r.json()["total"] == len(compute_critical(raw, base_scope, today, "2003")) >= 1, "critical?text= filtra por N° de crédito")
    check(all((i["severity"] == "critical") == (i["days_overdue"] >= 30) for i in flat), "severidad coherente con 30 días")

    print("== 3. Filtros ruta / recaudador / combinados ==")
    collectors = {c["full_name"]: c["id"] for c in (await api.call(sup, "GET", "/reports/dashboard/filters")).json()["collectors"]}
    cases = [("ruta Norte", {"route_id": str(routes["Ruta Norte"].id)}), ("ruta Centro", {"route_id": str(routes["Ruta Centro"].id)}),
             ("ruta Sur", {"route_id": str(routes["Ruta Sur"].id)}), ("days=30", {"days": 30})]
    for name, cid in collectors.items():
        cases.append((f"recaudador {name}", {"collector_id": cid}))
    for label, params in cases:
        scope = scope_of(raw, brand_id=norte.id, partner_id=None, route_id=UUID(params["route_id"]) if "route_id" in params else None,
                         collector_id=UUID(params["collector_id"]) if "collector_id" in params else None)
        r = await api.call(sup, "GET", "/reports/dashboard/summary", params=params)
        body = r.json()
        problems = diff(compute_summary(raw, scope, today, params.get("days", 90)), {k2: v for k2, v in body.items() if k2 != "critical_days"})
        check(r.status_code == 200 and not problems, f"summary con {label} == oráculo", "; ".join(problems[:4]) or r.text[:150])
    filters = (await api.call(sup, "GET", "/reports/dashboard/filters")).json()
    names = sorted(r["name"] for r in filters["routes"])
    check({"Ruta Norte", "Ruta Centro", "Ruta Sur"} <= set(names), "filters lista las rutas demo")
    check(all(set(r["collector_ids"]) <= {c["id"] for c in filters["collectors"]} for r in filters["routes"]), "filters: collector_ids ⊆ recaudadores listados")
    one_collector = next(iter(collectors.values()))
    r = await api.call(sup, "GET", "/reports/dashboard/filters", params={"collector_id": one_collector})
    check(len(r.json()["routes"]) == len(filters["routes"]), "filters ignora route/collector (selectores completos)")

    print("== 4. Semanal / Anual ==")
    for mode in ("weekly", "annual"):
        for on_date in (None, today - timedelta(days=40), date(today.year - 1, 6, 15)):
            params = {"mode": mode, **({"date": on_date.isoformat()} if on_date else {})}
            body = (await api.call(sup, "GET", "/reports/period", params=params)).json()
            exp = compute_period(raw, base_scope, today, mode, on_date)
            problems = diff(exp, {k2: v for k2, v in body.items() if k2 not in ("mode",)} | {"buckets": [{k3: v3 for k3, v3 in b.items() if k3 != "key"} for b in body["buckets"]]})
            check(len(body["buckets"]) == (7 if mode == "weekly" else 12) and not problems,
                  f"period {mode} date={on_date or 'omitida'} == oráculo", "; ".join(problems[:4]))
            if on_date is None:
                check(date.fromisoformat(body["start"]).weekday() == 0 if mode == "weekly" else body["start"].endswith("-01-01"), f"period {mode}: inicio correcto")

    print("== 5. Seguridad y alcance ==")
    r = await api.call(partner, "GET", "/reports/dashboard/filters")
    route_names = {x["name"] for x in r.json()["routes"]}
    check(route_names == {"Ruta Norte", "Ruta Centro"}, "socio (qd_laura) solo ve sus rutas", str(route_names))
    r = await api.call(partner, "GET", "/reports/dashboard/summary")
    scope_p = scope_of(raw, brand_id=norte.id, partner_id=partner.id, route_id=None, collector_id=None)
    problems = diff(compute_summary(raw, scope_p, today, 90), {k2: v for k2, v in r.json().items() if k2 != "critical_days"})
    check(not problems and all(x["route_name"] != "Ruta Sur" for x in r.json()["by_route"]), "socio: summary == oráculo y sin Ruta Sur", "; ".join(problems[:4]))
    r = await api.call(partner, "GET", "/reports/dashboard/summary", params={"route_id": str(routes["Ruta Sur"].id)})
    check(r.status_code == 404, "socio pidiendo la Ruta Sur → 404")
    sur_admin = users["admin_sur"]
    r = await api.call(sur_admin, "GET", "/reports/dashboard/summary", params={"brand_id": str(norte.id)})
    check(r.status_code == 200 and r.json()["kpis"]["portfolio_total"] == 0 and r.json()["by_route"] == [], "admin_sur con brand_id de Norte → sin datos de Norte")
    r = await api.call(sur_admin, "GET", "/reports/dashboard/summary", params={"route_id": str(routes["Ruta Norte"].id)})
    check(r.status_code == 404, "admin_sur con route_id de Norte → 404")
    r = await api.call(sur_admin, "GET", "/reports/portfolio", params={"brand_id": str(norte.id)})
    check(r.status_code == 200 and r.json() == [], "admin_sur: /portfolio no filtra otras marcas aunque mande brand_id")
    for path in ("/reports/dashboard/filters", "/reports/dashboard/summary", "/reports/dashboard/critical", "/reports/period?mode=weekly"):
        r = await api.call(users["collector_01"], "GET", path)
        check(r.status_code == 403, f"recaudador 403 en {path.split('?')[0]}")
    r_all = await api.call(dev, "GET", "/reports/dashboard/summary")
    scope_all = scope_of(raw, brand_id=None, partner_id=None, route_id=None, collector_id=None)
    problems = diff(compute_summary(raw, scope_all, today, 90), {k2: v for k2, v in r_all.json().items() if k2 != "critical_days"})
    check(not problems, "dev sin brand_id (todas las marcas) == oráculo", "; ".join(problems[:4]))
    r = await api.call(dev, "GET", "/reports/dashboard/summary", params={"brand_id": str(norte.id)})
    problems = diff(compute_summary(raw, base_scope, today, 90), {k2: v for k2, v in r.json().items() if k2 != "critical_days"})
    check(not problems, "dev con brand_id de Norte == oráculo de Norte", "; ".join(problems[:4]))
    r = await api.call(sup, "GET", "/reports/dashboard/summary", params={"route_id": "00000000-0000-0000-0000-000000000000"})
    check(r.status_code == 404, "route_id inexistente → 404")
    r = await api.call(sur_admin, "GET", "/reports/dashboard/summary")
    check(r.status_code == 200 and r.json()["kpis"]["portfolio_total"] == 0 and r.json()["daily"] == [], "marca sin créditos → ceros (no 500)")
    r = await api.call(sur_admin, "GET", "/reports/period", params={"mode": "annual"})
    check(r.status_code == 200 and len(r.json()["buckets"]) == 12 and r.json()["totals"]["margin"] == 0, "period sin datos → 12 buckets en 0")

    print("== 6. Validaciones de borde ==")
    for label, path, params in (("days=0", "/reports/dashboard/summary", {"days": 0}), ("days=366", "/reports/dashboard/summary", {"days": 366}),
                                ("mode inválido", "/reports/period", {"mode": "monthly"}), ("date inválida", "/reports/period", {"mode": "weekly", "date": "2026-13-45"}),
                                ("page_size=101", "/reports/dashboard/critical", {"page_size": 101}), ("page=0", "/reports/dashboard/critical", {"page": 0})):
        r = await api.call(sup, "GET", path, params=params)
        check(r.status_code == 422, f"{label} → 422")
    r = await api.call(sup, "GET", "/reports/dashboard/critical", params={"page": 999})
    check(r.status_code == 200 and r.json()["items"] == [], "page fuera de rango → lista vacía")

    print("== 7. Día de Colombia (corte 19:00) ==")
    check(today_bogota(datetime(2026, 11, 8, 2, 0, tzinfo=timezone.utc)) == date(2026, 11, 7), "02:00 UTC sigue siendo el día anterior en Colombia")
    check(today_bogota(datetime(2026, 11, 8, 5, 0, tzinfo=timezone.utc)) == date(2026, 11, 8), "05:00 UTC ya es el día nuevo en Colombia")

    if mutate:
        await mutations(api, sup, routes, today)

    failed = [name for ok, name in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN: {failed}" if failed else ""))
    return 1 if failed else 0


async def kpis_of(api, user):
    body = (await api.call(user, "GET", "/reports/dashboard/summary")).json()
    return body["kpis"], {p["date"]: p for p in body["daily"]}


async def mutations(api: Api, sup: UserModel, routes: dict, today: date) -> None:
    """Operaciones reales con los endpoints de la app; los datos creados se CONSERVAN."""
    print("== 8. Operaciones en vivo (se conservan) ==")
    async with async_session() as db:
        # Cuota demo sin abonos que ya venció o vence hoy (el backend rechaza abonar cuotas futuras).
        pending = (await db.execute(
            select(PaymentModel).join(LoanModel, LoanModel.id == PaymentModel.loan_id)
            .where(LoanModel.loan_number.between(2001, 2012), LoanModel.active.is_(True),
                   PaymentModel.pay_date <= today, func.coalesce(PaymentModel.applied, 0) == 0)
            .order_by(PaymentModel.pay_date.desc(), PaymentModel.quota_number)
        )).scalars().first()
        concept = (await db.execute(select(ExpenseConceptModel).where(ExpenseConceptModel.concept == "Combustible", ExpenseConceptModel.brand_id == sup.brand_id))).scalars().first()
    before, daily_before = await kpis_of(api, sup)

    # a) registrar el cobro de una cuota
    value = float(pending.value)
    r = await api.call(sup, "PUT", f"/payments/{pending.id}/pay", params={"value": value})
    after, daily_after = await kpis_of(api, sup)
    check(r.status_code == 200, "PUT /payments/{id}/pay 200", r.text[:150])
    check(abs(after["total_paid"] - before["total_paid"] - value) <= TOL and abs(before["portfolio_total"] - after["portfolio_total"] - value) <= TOL,
          f"pago de ${value:,.0f}: total_paid sube y cartera baja exactamente ese valor")
    day = today.isoformat()
    check(abs(daily_after[day]["collected"] - daily_before.get(day, {"collected": 0})["collected"] - value) <= TOL, "cobro diario de hoy sube exactamente el pago")
    # b) gasto
    period_before = (await api.call(sup, "GET", "/reports/period", params={"mode": "weekly", "date": today.isoformat()})).json()["totals"]
    r = await api.call(sup, "POST", "/expenses/", json={"date": today.isoformat(), "value": 11000, "name": "QA gasto en vivo", "expensesconcept_id": str(concept.id), "route_id": str(routes["Ruta Norte"].id)})
    period_after = (await api.call(sup, "GET", "/reports/period", params={"mode": "weekly", "date": today.isoformat()})).json()["totals"]
    check(r.status_code == 201, "POST /expenses 201", r.text[:150])
    check(abs(period_after["expenses"] - period_before["expenses"] - 11000) <= TOL and abs(period_before["profit"] - period_after["profit"] - 11000) <= TOL,
          "gasto de $11.000: gastos semanal sube y utilidad baja exactamente eso")
    # c) cliente + crédito nuevo
    stamp = datetime.now().strftime("%H%M%S")
    r = await api.call(sup, "POST", "/clients/", json={
        "full_name": f"QD Cliente Nuevo {stamp}", "id_document": f"QD-N{stamp}", "current_address": "Calle QA", "current_phone": "3000000000",
        "current_mobile": "3000000000", "neighborhood": "QA", "linking_date": datetime.now().isoformat(), "routes_ids": [str(routes["Ruta Sur"].id)], "brand_id": str(sup.brand_id)})
    check(r.status_code == 201, "POST /clients 201", r.text[:150])
    client = r.json()
    crs = (await api.call(sup, "GET", "/clientroute/", params={"route_id": str(routes["Ruta Sur"].id)})).json()
    cr = next(c for c in crs if c["client_id"] == client["id"])
    mid, _ = await kpis_of(api, sup)
    now = datetime.now()
    r = await api.call(sup, "POST", "/loans/", json={
        "loan_number": int(f"9{stamp}"), "initial_date": now.isoformat(), "end_date": (now + timedelta(days=60)).isoformat(), "value_quota_fixed": 6000,
        "agreed_quotas": 10, "date_first_quota": (now + timedelta(days=1)).isoformat(), "payment_method": "semanal", "value_capital": 50000,
        "value_utility_loan": 10000, "value_total_loan": 60000, "interest_rate": 20, "current_address": "Calle QA", "current_mobile": "3000000000",
        "clientroute_id": cr["id"], "client_id": client["id"]})
    after_loan, _ = await kpis_of(api, sup)
    check(r.status_code == 201, "POST /loans 201", r.text[:150])
    check(abs(after_loan["portfolio_total"] - mid["portfolio_total"] - 60000) <= TOL and after_loan["portfolio_loans"] == mid["portfolio_loans"] + 1,
          "crédito de $60.000: cartera sube exactamente ese valor y +1 crédito vigente")
    check(mid["clients_active"] == before["clients_active"] + 1, "cliente nuevo: +1 cliente activo")
    # d) desactivar el cliente
    r = await api.call(sup, "PUT", f"/clients/{client['id']}/toggle")
    final, _ = await kpis_of(api, sup)
    check(r.status_code == 200 and final["clients_inactive"] == mid["clients_inactive"] + 1 and final["clients_active"] == mid["clients_active"] - 1,
          "desactivar cliente: +1 inactivo y −1 activo")
    # conciliación final contra el oráculo con los datos ya operados
    async with async_session() as db:
        raw = await load_raw(db)
    scope = scope_of(raw, brand_id=sup.brand_id, partner_id=None, route_id=None, collector_id=None)
    body = (await api.call(sup, "GET", "/reports/dashboard/summary")).json()
    problems = diff(compute_summary(raw, scope, today, 90), {k2: v for k2, v in body.items() if k2 != "critical_days"})
    check(not problems, "tras operar datos: summary sigue == oráculo", "; ".join(problems[:4]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QA de Reportes (no borra datos)")
    parser.add_argument("--mutate", action="store_true", help="Opera datos reales (pago, gasto, cliente, crédito) y verifica deltas")
    sys.exit(asyncio.run(main(parser.parse_args().mutate)))
