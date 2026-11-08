"""Oráculo independiente de los reportes (Resumen, mora crítica, Semanal/Anual).

Lee las filas crudas de las tablas y calcula todo con bucles de Python puro — sin `loan_stats`, sin
agregados SQL — siguiendo las definiciones del plan:

* pagado = Σ applied · saldo = value_total_loan − pagado · cartera = crédito activo con saldo > 0
* cuota vencida = pay_date < hoy y value − applied > 0.01 · mora = LEAST(Σ vencidas, saldo)
* días de mora = hoy − MIN(pay_date vencida) · crítica si ≥ 30 días

Lo usan `seed_dashboard_demo.py` (para verificar el escenario sembrado) y `qa_reports.py` (para comparar
contra la API en cualquier estado de la base, incluso después de operar datos).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select

CRITICAL_DAYS = 30
UNPAID_TOLERANCE = 0.01


@dataclass
class Raw:
    routes: List[dict]
    collectors: List[dict]
    client_routes: List[dict]
    clients: Dict[UUID, dict]
    loans: List[dict]
    payments_by_loan: Dict[UUID, List[dict]]
    payments: List[dict]
    expenses: List[dict]


async def load_raw(db) -> Raw:
    from app.infrastructure.models.client_model import ClientModel
    from app.infrastructure.models.client_route_model import ClientRouteModel
    from app.infrastructure.models.expense_model import ExpenseModel
    from app.infrastructure.models.loan_model import LoanModel
    from app.infrastructure.models.models import UserType
    from app.infrastructure.models.payment_model import PaymentModel
    from app.infrastructure.models.route_model import RouteModel
    from app.infrastructure.models.user_model import UserModel

    routes = [
        {"id": r.id, "name": r.name, "brand_id": r.brand_id, "active": bool(r.active), "allowed": list(r.allowed_users_ids or [])}
        for r in (await db.execute(select(RouteModel))).scalars().all()
    ]
    collectors = [
        {"id": u.id, "full_name": u.full_name or u.username, "brand_id": u.brand_id}
        for u in (await db.execute(select(UserModel).where(UserModel.type_user == UserType.collector, UserModel.active == True))).scalars().all()
    ]
    client_routes = [
        {"id": cr.id, "client_id": cr.cliente_id, "route_id": cr.route_id}
        for cr in (await db.execute(select(ClientRouteModel))).scalars().all()
    ]
    clients = {
        c.id: {"id": c.id, "name": c.full_name, "document": c.id_document, "phone": c.current_mobile or c.current_phone, "active": bool(c.active)}
        for c in (await db.execute(select(ClientModel))).scalars().all()
    }
    loans = [
        {
            "id": l.id, "number": l.loan_number, "clientroute_id": l.clientroute_id,
            "total": float(l.value_total_loan or 0), "active": bool(l.active),
        }
        for l in (await db.execute(select(LoanModel))).scalars().all()
    ]
    payments = [
        {
            "loan_id": p.loan_id, "pay_date": p.pay_date, "payment_date": p.payment_date,
            "value": float(p.value or 0), "applied": float(p.applied or 0),
        }
        for p in (await db.execute(select(PaymentModel))).scalars().all()
    ]
    by_loan: Dict[UUID, List[dict]] = defaultdict(list)
    for p in payments:
        by_loan[p["loan_id"]].append(p)
    expenses = [
        {"date": e.date, "value": float(e.value or 0), "route_id": e.route_id, "active": bool(e.active)}
        for e in (await db.execute(select(ExpenseModel))).scalars().all()
    ]
    return Raw(routes, collectors, client_routes, clients, loans, dict(by_loan), payments, expenses)


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 2) if whole else 0.0


def scope_of(raw: Raw, *, brand_id: Optional[UUID], partner_id: Optional[UUID], route_id: Optional[UUID], collector_id: Optional[UUID]) -> dict:
    collectors = {c["id"]: c for c in raw.collectors if brand_id is None or c["brand_id"] == brand_id}
    all_routes = []
    for r in sorted(raw.routes, key=lambda x: (x["name"], str(x["id"]))):
        if not r["active"] or (brand_id and r["brand_id"] != brand_id):
            continue
        if partner_id and partner_id not in r["allowed"]:
            continue
        all_routes.append({"id": r["id"], "name": r["name"], "collector_ids": [u for u in r["allowed"] if u in collectors]})
    assigned = {u for r in all_routes for u in r["collector_ids"]}
    all_collectors = [c for c in sorted(collectors.values(), key=lambda x: (x["full_name"], str(x["id"]))) if c["id"] in assigned]

    routes = all_routes
    if collector_id:
        routes = [r for r in routes if collector_id in r["collector_ids"]]
    if route_id:
        routes = [r for r in routes if r["id"] == route_id]
    return {"all_routes": all_routes, "all_collectors": all_collectors, "routes": routes, "collector_id": collector_id}


def loan_stats(raw: Raw, today: date) -> Dict[UUID, dict]:
    stats = {}
    for loan in raw.loans:
        payments = raw.payments_by_loan.get(loan["id"], [])
        paid = sum(p["applied"] for p in payments)
        balance = loan["total"] - paid
        overdue = [p for p in payments if p["pay_date"] < today and p["value"] - p["applied"] > UNPAID_TOLERANCE]
        overdue_raw = sum(p["value"] - p["applied"] for p in overdue)
        since = min((p["pay_date"] for p in overdue), default=None)
        stats[loan["id"]] = {
            "paid": paid,
            "balance": balance,
            "overdue_amount": min(overdue_raw, balance) if overdue else 0.0,
            "overdue_quotas": len(overdue),
            "overdue_since": since,
            "days_overdue": (today - since).days if since else None,
        }
    return stats


def _loans_in_scope(raw: Raw, route_ids: set) -> List[dict]:
    route_of = {cr["id"]: cr for cr in raw.client_routes}
    out = []
    for loan in raw.loans:
        cr = route_of.get(loan["clientroute_id"])
        if cr and cr["route_id"] in route_ids:
            out.append({**loan, "route_id": cr["route_id"], "client_id": cr["client_id"]})
    return out


def compute_summary(raw: Raw, scope: dict, today: date, days: int) -> dict:
    route_ids = {r["id"] for r in scope["routes"]}
    stats = loan_stats(raw, today)
    loans = [l for l in _loans_in_scope(raw, route_ids) if l["active"]]

    per_route = defaultdict(lambda: {"loans": 0, "active": 0.0, "lent": 0.0, "paid": 0.0, "late_loans": 0, "late": 0.0, "mild": 0.0, "critical": 0.0})
    critical_clients = set()
    for loan in loans:
        s = stats[loan["id"]]
        row = per_route[loan["route_id"]]
        if s["balance"] > 0:
            row["loans"] += 1
            row["active"] += s["balance"]
            row["lent"] += loan["total"]
            row["paid"] += s["paid"]
        if s["overdue_amount"] > 0:
            row["late_loans"] += 1
            row["late"] += s["overdue_amount"]
            if s["days_overdue"] >= CRITICAL_DAYS:
                row["critical"] += s["overdue_amount"]
                critical_clients.add(loan["client_id"])
            else:
                row["mild"] += s["overdue_amount"]

    total = lambda key: sum(row[key] for row in per_route.values())  # noqa: E731
    clients_in_scope = {cr["client_id"] for cr in raw.client_routes if cr["route_id"] in route_ids}
    clients_active = sum(1 for cid in clients_in_scope if raw.clients[cid]["active"])
    clients_inactive = len(clients_in_scope) - clients_active

    def collectors_of(route):
        return [c for c in scope["all_collectors"] if c["id"] in route["collector_ids"] and (not scope["collector_id"] or c["id"] == scope["collector_id"])]

    by_route = []
    for route in scope["routes"]:
        row = per_route.get(route["id"]) or {"active": 0.0, "late": 0.0}
        by_route.append({
            "route_id": route["id"], "route_name": route["name"],
            "collector_names": [c["full_name"] for c in collectors_of(route)],
            "active": round(row["active"], 2), "late": round(row["late"], 2), "rate": _pct(row["late"], row["active"]),
        })
    by_route.sort(key=lambda r: r["active"], reverse=True)

    by_collector = []
    for collector in scope["all_collectors"]:
        if scope["collector_id"] and collector["id"] != scope["collector_id"]:
            continue
        assigned = [r for r in scope["routes"] if collector["id"] in r["collector_ids"]]
        if not assigned:
            continue
        goal = sum((per_route.get(r["id"]) or {"lent": 0.0})["lent"] for r in assigned)
        collected = sum((per_route.get(r["id"]) or {"paid": 0.0})["paid"] for r in assigned)
        by_collector.append({
            "collector_id": collector["id"], "full_name": collector["full_name"], "route_names": [r["name"] for r in assigned],
            "goal": round(goal, 2), "collected": round(collected, 2), "percent": _pct(collected, goal),
        })
    by_collector.sort(key=lambda r: r["percent"], reverse=True)

    start = today - timedelta(days=days - 1)
    route_of = {cr["id"]: cr["route_id"] for cr in raw.client_routes}
    loan_route = {l["id"]: route_of.get(l["clientroute_id"]) for l in raw.loans}
    daily: Dict[date, dict] = {}
    for p in raw.payments:
        if loan_route.get(p["loan_id"]) not in route_ids:
            continue
        if start <= p["pay_date"] <= today:
            daily.setdefault(p["pay_date"], {"date": p["pay_date"], "collected": 0.0, "goal": 0.0})["goal"] += p["value"]
        if p["payment_date"] and start <= p["payment_date"] <= today:
            daily.setdefault(p["payment_date"], {"date": p["payment_date"], "collected": 0.0, "goal": 0.0})["collected"] += p["applied"]
    daily_points = [{"date": d, "collected": round(v["collected"], 2), "goal": round(v["goal"], 2)} for d, v in sorted(daily.items())]

    portfolio_total, late_total = total("active"), total("late")
    in_field = {c["id"] for r in scope["routes"] for c in collectors_of(r)}
    return {
        "kpis": {
            "portfolio_total": round(portfolio_total, 2), "portfolio_loans": total("loans"),
            "delinquency_total": round(late_total, 2), "delinquency_loans": total("late_loans"),
            "delinquency_rate": _pct(late_total, portfolio_total),
            "total_lent": round(total("lent"), 2), "total_paid": round(total("paid"), 2),
            "effectiveness": min(100.0, _pct(total("paid"), total("lent"))),
            "clients_active": clients_active, "clients_inactive": clients_inactive,
            "active_rate": _pct(clients_active, len(clients_in_scope)),
            "routes_total": len(scope["routes"]),
            "routes_with_loans": sum(1 for r in scope["routes"] if (per_route.get(r["id"]) or {"loans": 0})["loans"] > 0),
            "collectors_in_field": len(in_field), "critical_clients": len(critical_clients),
        },
        "daily": daily_points,
        "composition": {"up_to_date": round(portfolio_total - late_total, 2), "mild": round(total("mild"), 2), "critical": round(total("critical"), 2)},
        "by_route": by_route,
        "by_collector": by_collector,
        "average_goal": round(sum(r["goal"] for r in by_collector) / len(by_collector), 2) if by_collector else 0.0,
    }


def compute_critical(raw: Raw, scope: dict, today: date, text: Optional[str] = None) -> List[dict]:
    route_ids = {r["id"] for r in scope["routes"]}
    stats = loan_stats(raw, today)
    route_by_id = {r["id"]: r for r in scope["routes"]}
    items = []
    for loan in _loans_in_scope(raw, route_ids):
        s = stats[loan["id"]]
        if not loan["active"] or s["overdue_amount"] <= 0:
            continue
        client = raw.clients[loan["client_id"]]
        if text and text.strip().lower() not in client["name"].lower() and text.strip() not in str(loan["number"]):
            continue
        route = route_by_id[loan["route_id"]]
        items.append({
            "client_id": loan["client_id"], "client_name": client["name"], "client_document": client["document"],
            "route_id": route["id"], "route_name": route["name"],
            "loan_id": loan["id"], "loan_number": loan["number"], "loan_balance": round(s["balance"], 2),
            "overdue_amount": round(s["overdue_amount"], 2), "overdue_quotas": s["overdue_quotas"],
            "overdue_since": s["overdue_since"], "days_overdue": s["days_overdue"],
            "severity": "critical" if s["days_overdue"] >= CRITICAL_DAYS else "warning",
        })
    items.sort(key=lambda i: (-i["overdue_amount"], str(i["loan_id"])))
    return items


def compute_period(raw: Raw, scope: dict, today: date, mode: str, on_date: Optional[date]) -> dict:
    route_ids = {r["id"] for r in scope["routes"]}
    route_of = {cr["id"]: cr["route_id"] for cr in raw.client_routes}
    loan_route = {l["id"]: route_of.get(l["clientroute_id"]) for l in raw.loans}
    incomes = [(p["payment_date"], p["applied"]) for p in raw.payments if p["payment_date"] and loan_route.get(p["loan_id"]) in route_ids]
    costs = [(e["date"], e["value"]) for e in raw.expenses if e["active"] and e["route_id"] in route_ids]
    dates = [d for d, _ in incomes + costs]
    latest = max(dates) if dates else None
    ref = on_date or latest or today

    if mode == "weekly":
        start = ref - timedelta(days=ref.weekday())
        buckets = [start + timedelta(days=i) for i in range(7)]
        end = start + timedelta(days=6)
        bucket_of = lambda d: d  # noqa: E731
    else:
        start, end = date(ref.year, 1, 1), date(ref.year, 12, 31)
        buckets = [date(ref.year, m, 1) for m in range(1, 13)]
        bucket_of = lambda d: date(d.year, d.month, 1)  # noqa: E731

    collected = {b: 0.0 for b in buckets}
    expenses = {b: 0.0 for b in buckets}
    for d, v in incomes:
        if start <= d <= end:
            collected[bucket_of(d)] += v
    for d, v in costs:
        if start <= d <= end:
            expenses[bucket_of(d)] += v
    rows = [{"date": b, "collected": round(collected[b], 2), "expenses": round(expenses[b], 2), "profit": round(collected[b] - expenses[b], 2)} for b in buckets]
    tc, te = round(sum(collected.values()), 2), round(sum(expenses.values()), 2)
    return {
        "start": start, "end": end, "latest_movement_date": latest, "buckets": rows,
        "totals": {"collected": tc, "expenses": te, "profit": round(tc - te, 2), "margin": round((tc - te) / tc * 100, 2) if tc else 0.0},
    }
