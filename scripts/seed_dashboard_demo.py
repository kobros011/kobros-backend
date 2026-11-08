#!/usr/bin/env python3
"""
Datos demo para QA de Reportes (Resumen, Semanal, Anual). Marca NORTE01.

Idempotente y NUNCA borra: cada entidad se busca por clave natural (`username` `qd_*`, nombre de ruta,
`id_document` `QD-*`, `loan_number` 2001–2012) y solo se crea si falta. Los pagos se escriben
retroactivamente replicando las transiciones de `PaymentRepository.pay_payment` (status, applied,
payment_date, canceled/pending_quotas, total_default, beak) y todas las fechas son relativas a hoy
(hora Colombia), así que el escenario siempre cubre las mismas situaciones:

  3 al día · 3 mora leve (5, 15, 25 días; una con pago parcial) · 3 mora crítica (45, 75, 110 días)
  1 pagado completo (excluido) · 1 con sobrepago · 1 crédito inactivo (excluido)

Al terminar corre el oráculo (`report_oracle.py`) y verifica la mora esperada de cada crédito.

Uso (desde el contenedor api):  python scripts/seed_dashboard_demo.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.main  # noqa: F401,E402  (registra todos los modelos para resolver relaciones por nombre)
from sqlalchemy import select  # noqa: E402

from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session, engine  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.client_model import ClientModel  # noqa: E402
from app.infrastructure.models.client_route_model import ClientRouteModel  # noqa: E402
from app.infrastructure.models.expense_model import ExpenseConceptModel, ExpenseModel  # noqa: E402
from app.infrastructure.models.loan_model import LoanModel  # noqa: E402
from app.infrastructure.models.models import UserType  # noqa: E402
from app.infrastructure.models.payment_model import PaymentModel  # noqa: E402
from app.infrastructure.models.route_model import RouteModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from app.infrastructure.utils.timedelta_pay_date import add_months  # noqa: E402
from scripts.report_oracle import compute_critical, load_raw, scope_of  # noqa: E402

engine.echo = False  # el engine imprime cada SQL por defecto; aquí solo interesa el resumen
logging.disable(logging.CRITICAL)

BRAND_CODE = "NORTE01"
STEP_DAYS = {"semanal": 7, "quincenal": 14, "diaria": 1}


@dataclass(frozen=True)
class LoanSpec:
    number: int
    client: str
    route: str
    method: str
    quota: float
    agreed: int
    first_offset: int  # días respecto a hoy de la primera cuota (negativo = pasado); None si es mensual
    behavior: tuple  # ("due",) | ("all",) | ("unpaid_from", j) | ("partial", j, ratio) | ("over", idx, ratio)
    active: bool = True
    expect_days: int | None = None  # días de mora esperados (None = sin mora)
    expect_overdue: float | None = None


USERS = (
    ("qd_carlos", "Carlos Vargas (Recaudador)", UserType.collector),
    ("qd_julian", "Julián Ortiz (Recaudador)", UserType.collector),
    ("qd_andres", "Andrés Pérez (Recaudador)", UserType.collector),
    ("qd_laura", "Laura Patiño (Socia)", UserType.partner),
)

# ruta -> usuarios asignados (username); admin_norte se agrega si existe
ROUTES = {
    "Ruta Norte": ("qd_carlos", "qd_laura", "admin_norte"),
    "Ruta Centro": ("qd_andres", "qd_laura"),
    "Ruta Sur": ("qd_julian",),
}

CLIENTS = (
    ("Juan Pérez Rendón", "Ruta Norte", True), ("María Fernanda Gómez", "Ruta Norte", True),
    ("Pedro Alonso Ruiz", "Ruta Norte", True), ("Sandra Milena Díaz", "Ruta Norte", True),
    ("Luis Fernando Herrera", "Ruta Centro", True), ("Andrés Felipe Zapata", "Ruta Centro", True),
    ("Diana Carolina Mejía", "Ruta Centro", True), ("Hugo Armando León", "Ruta Centro", True),
    ("Natalia Vanessa Correa", "Ruta Sur", True), ("Camilo Andrés Torres", "Ruta Sur", True),
    ("Paola Andrea Rojas", "Ruta Sur", False), ("Sergio Iván Castaño", "Ruta Sur", True),
)

LOANS = (
    LoanSpec(2001, "Juan Pérez Rendón", "Ruta Norte", "semanal", 50000, 20, -63, ("due",)),
    LoanSpec(2002, "María Fernanda Gómez", "Ruta Norte", "semanal", 40000, 16, -67, ("unpaid_from", 6), expect_days=25, expect_overdue=160000),
    LoanSpec(2003, "Pedro Alonso Ruiz", "Ruta Norte", "quincenal", 120000, 10, -73, ("unpaid_from", 2), expect_days=45, expect_overdue=480000),
    LoanSpec(2004, "Sandra Milena Díaz", "Ruta Norte", "diaria", 15000, 60, -45, ("due",)),
    LoanSpec(2005, "Luis Fernando Herrera", "Ruta Centro", "semanal", 60000, 20, -96, ("unpaid_from", 3), expect_days=75, expect_overdue=660000),
    LoanSpec(2006, "Andrés Felipe Zapata", "Ruta Centro", "quincenal", 90000, 12, -71, ("partial", 4, 0.4), expect_days=15, expect_overdue=144000),
    LoanSpec(2007, "Diana Carolina Mejía", "Ruta Centro", "mensual", 200000, 6, 0, ("due",)),
    LoanSpec(2008, "Hugo Armando León", "Ruta Centro", "semanal", 25000, 10, -63, ("all",)),
    LoanSpec(2009, "Natalia Vanessa Correa", "Ruta Sur", "semanal", 70000, 20, -117, ("unpaid_from", 1), expect_days=110, expect_overdue=1120000),
    LoanSpec(2010, "Camilo Andrés Torres", "Ruta Sur", "quincenal", 80000, 12, -47, ("unpaid_from", 3), expect_days=5, expect_overdue=80000),
    LoanSpec(2011, "Paola Andrea Rojas", "Ruta Sur", "semanal", 45000, 10, -35, ("over", 2, 1.5)),
    LoanSpec(2012, "Sergio Iván Castaño", "Ruta Sur", "semanal", 55000, 10, -42, ("unpaid_from", 1), active=False),
)

EXPENSES = (  # (días atrás, ruta, concepto, valor, nombre, activo)
    (3, "Ruta Norte", "Combustible", 18000, "Gasolina moto cobro", True),
    (9, "Ruta Centro", "Alimentación", 12500, "Almuerzo recorrido", True),
    (16, "Ruta Sur", "Combustible", 20000, "Gasolina moto cobro", True),
    (24, "Ruta Norte", "Alimentación", 15000, "Almuerzo recorrido", True),
    (37, "Ruta Centro", "Combustible", 25000, "Gasolina moto cobro", True),
    (44, "Ruta Sur", "Alimentación", 9999, "Gasto anulado (inactivo)", False),
)
CONCEPTS = {"Combustible": ("FaGasPump", "#fa8c16"), "Alimentación": ("FaUtensils", "#52c41a")}


def schedule(spec: LoanSpec, today: date) -> list[date]:
    first = add_months(today, -3) if spec.method == "mensual" else today + timedelta(days=spec.first_offset)
    if spec.method == "mensual":
        return [add_months(first, i) for i in range(spec.agreed)]
    step = STEP_DAYS[spec.method]
    return [first + timedelta(days=step * i) for i in range(spec.agreed)]


def build_payments(spec: LoanSpec, today: date) -> tuple[list[dict], dict]:
    """Pagos del crédito + estado final del crédito/cliente según las reglas de `pay_payment`."""
    dates = schedule(spec, today)
    payments, canceled, default, beak = [], 0, 0.0, 0.0
    kind = spec.behavior[0]
    for i, pay_date in enumerate(dates):
        q = i + 1
        status, applied = "pendiente", 0.0
        if kind == "all":
            paid = True
        elif kind == "due":
            paid = pay_date < today
        elif kind == "unpaid_from":
            paid = i < spec.behavior[1]
        elif kind == "partial":
            paid = i < spec.behavior[1]
        else:  # over
            paid = pay_date < today
        if paid:
            applied = spec.quota
            status = "pagado"
            if kind == "over" and i == spec.behavior[1]:
                applied = round(spec.quota * spec.behavior[2], 2)
                beak += applied - spec.quota
        if kind == "partial" and i == spec.behavior[1]:
            applied = round(spec.quota * spec.behavior[2], 2)
            status = "mora"
            default += spec.quota - applied
        if status != "pendiente":
            late = 1 if (spec.number + q) % 4 == 0 else 0
            payment_date = min(today, pay_date + timedelta(days=late))
            canceled = q
        else:
            payment_date = None
        payments.append({"quota_number": q, "pay_date": pay_date, "payment_date": payment_date, "applied": applied, "status": status})
    return payments, {"canceled": canceled, "pending": spec.agreed - canceled, "default": round(default, 2), "beak": round(beak, 2), "end": dates[-1], "first": dates[0]}


async def ensure(session, model, where, create, label, dry_run):
    found = (await session.execute(select(model).where(*where))).scalars().first()
    if found:
        return found, False
    if dry_run:
        print(f"[dry-run] CREAR {label}")
        return None, True
    obj = create()
    session.add(obj)
    await session.flush()
    print(f"CREADO {label}")
    return obj, True


async def run(dry_run: bool) -> int:
    today = today_bogota()
    async with async_session() as s:
        brand = (await s.execute(select(BrandModel).where(BrandModel.code == BRAND_CODE))).scalars().first()
        if not brand:
            print(f"No existe la marca {BRAND_CODE}; ejecuta primero scripts/seed_test_data.py")
            return 1

        users = {}
        for username, full_name, type_user in USERS:
            user, _ = await ensure(
                s, UserModel, [UserModel.username == username],
                lambda u=username, n=full_name, t=type_user: UserModel(
                    username=u, full_name=n, email=f"{u}@kobros-demo.com", type_user=t,
                    document_id=f"QD-{u}", hashed_password="", brand_id=brand.id, mobile="3000000000",
                ),
                f"usuario {username}", dry_run,
            )
            users[username] = user
        admin = (await s.execute(select(UserModel).where(UserModel.username == "admin_norte"))).scalars().first()
        if admin:
            users["admin_norte"] = admin

        routes = {}
        for name, usernames in ROUTES.items():
            allowed = [users[u].id for u in usernames if users.get(u)]
            route, created = await ensure(
                s, RouteModel, [RouteModel.name == name, RouteModel.brand_id == brand.id],
                lambda n=name, a=allowed: RouteModel(
                    name=n, initial_value=5_000_000, initial_expense=100_000, opening_date=today - timedelta(days=200),
                    loans_number=0, allowed_users_ids=a, brand_id=brand.id,
                ),
                f"ruta {name}", dry_run,
            )
            if route is not None and not created and set(route.allowed_users_ids or []) != set(allowed):
                route.allowed_users_ids = allowed
                print(f"ACTUALIZADA ruta {name}: recaudadores asignados")
            routes[name] = route

        clients, client_routes, order = {}, {}, {}
        for full_name, route_name, active in CLIENTS:
            document = f"QD-{1001 + len(clients)}"
            client, created = await ensure(
                s, ClientModel, [ClientModel.id_document == document, ClientModel.brand_id == brand.id],
                lambda n=full_name, d=document, a=active: ClientModel(
                    full_name=n, id_document=d, current_address="Calle 10 #5-20", neighborhood="Centro",
                    current_phone="3010000000", current_mobile=f"30{(1000 + len(clients)):08d}"[:10],
                    linking_date=today - timedelta(days=180), beak=0, brand_id=brand.id, active=a,
                ),
                f"cliente {full_name}", dry_run,
            )
            clients[full_name] = client
            if client is None or routes[route_name] is None:
                continue
            order[route_name] = order.get(route_name, 0) + 1
            cr, _ = await ensure(
                s, ClientRouteModel, [ClientRouteModel.cliente_id == client.id, ClientRouteModel.route_id == routes[route_name].id],
                lambda c=client, r=routes[route_name], o=order[route_name]: ClientRouteModel(order=o, cliente_id=c.id, route_id=r.id),
                f"cliente-ruta {full_name} → {route_name}", dry_run,
            )
            client_routes[full_name] = cr

        for spec in LOANS:
            cr = client_routes.get(spec.client)
            if cr is None:
                continue
            existing = (await s.execute(select(LoanModel).where(LoanModel.clientroute_id == cr.id, LoanModel.loan_number == spec.number))).scalars().first()
            if existing:
                continue
            payments, state = build_payments(spec, today)
            total = spec.quota * spec.agreed
            capital = round(total / 1.2, 2)
            if dry_run:
                print(f"[dry-run] CREAR crédito {spec.number} ({spec.client}, {spec.method}, {len(payments)} cuotas)")
                continue
            loan = LoanModel(
                loan_number=spec.number, initial_date=state["first"] - timedelta(days=STEP_DAYS.get(spec.method, 30)), end_date=state["end"],
                value_quota_fixed=spec.quota, pending_quotas=state["pending"], canceled_quotas=state["canceled"], agreed_quotas=spec.agreed,
                total_default=state["default"], date_first_quota=state["first"], payment_method=spec.method,
                value_capital=capital, value_utility_loan=round(total - capital, 2), value_total_loan=total, interest_rate=20,
                clientroute_id=cr.id, active=spec.active,
            )
            s.add(loan)
            await s.flush()
            for p in payments:
                s.add(PaymentModel(
                    loan_id=loan.id, quota_number=p["quota_number"], pay_date=p["pay_date"], payment_date=p["payment_date"],
                    value=spec.quota, credit_value=total, status=p["status"], applied=p["applied"], liquidated=False,
                ))
            client = clients[spec.client]
            client.beak = float(client.beak or 0) + state["beak"]
            route = routes[spec.route]
            route.loans_number = max(route.loans_number or 0, spec.number)
            print(f"CREADO crédito {spec.number} ({spec.client}): {len(payments)} cuotas, pagadas {state['canceled']}")

        concepts = {}
        for name, (icon, color) in CONCEPTS.items():
            concepts[name], _ = await ensure(
                s, ExpenseConceptModel, [ExpenseConceptModel.concept == name, ExpenseConceptModel.brand_id == brand.id],
                lambda n=name, i=icon, c=color: ExpenseConceptModel(concept=n, keyIcon=i, color=c, brand_id=brand.id),
                f"concepto de gasto {name}", dry_run,
            )
        for days_ago, route_name, concept, value, name, active in EXPENSES:
            route, concept_obj = routes[route_name], concepts[concept]
            if route is None or concept_obj is None:
                continue
            day = today - timedelta(days=days_ago)
            await ensure(
                s, ExpenseModel, [ExpenseModel.route_id == route.id, ExpenseModel.date == day, ExpenseModel.value == value],
                lambda r=route, c=concept_obj, d=day, v=value, n=name, a=active: ExpenseModel(
                    date=d, value=v, name=n, expensesconcept_id=c.id, user_generated="Admin Norte (QA)", liquidated=False, route_id=r.id, active=a,
                ),
                f"gasto {name} {day}", dry_run,
            )

        if dry_run:
            await s.rollback()
            return 0
        await s.commit()

        # ---- verificación con el oráculo independiente --------------------------------
        raw = await load_raw(s)
        scope = scope_of(raw, brand_id=brand.id, partner_id=None, route_id=None, collector_id=None)
        critical = {item["loan_number"]: item for item in compute_critical(raw, scope, today)}
        failures = 0
        for spec in LOANS:
            item = critical.get(spec.number)
            if spec.expect_days is None:
                ok = item is None
                detail = "sin mora"
            else:
                ok = bool(item) and item["days_overdue"] == spec.expect_days and abs(item["overdue_amount"] - spec.expect_overdue) < 0.01
                detail = f"{spec.expect_days} días / ${spec.expect_overdue:,.0f}" + ("" if ok else f" (oráculo: {item and (item['days_overdue'], item['overdue_amount'])})")
            print(("OK   " if ok else "FALLA"), f"crédito {spec.number}: esperado {detail}")
            failures += 0 if ok else 1
        print("\nEscenario verificado." if not failures else f"\n{failures} crédito(s) no coinciden con lo esperado.")
        return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Datos demo para QA de Reportes (no borra nada)")
    parser.add_argument("--dry-run", action="store_true")
    sys.exit(asyncio.run(run(parser.parse_args().dry_run)))


if __name__ == "__main__":
    main()
