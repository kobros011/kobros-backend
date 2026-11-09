#!/usr/bin/env python3
"""
QA de la asignación de usuarios a rutas desde el usuario (GET/PUT/DELETE /users/{id}/routes) y de la validación de
`allowed_users_ids` en /routes. Crea sus propios usuarios y rutas ("QD RA"); no borra nada.

Comprueba: permisos (solo dev y super), asignar/quitar e idempotencia, acceso inmediato del cobrador, destinos inválidos
(dev/super, inactivo, otra marca, ruta ajena o inexistente), advertencia de pendientes (cobros sin liquidar y cierres
abiertos) sin impedir quitar, asignaciones simultáneas sin pisarse y la validación al guardar una ruta.

Uso (contenedor api):  python scripts/qa_route_assignment.py
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

import app.main  # noqa: E402,F401
from app.core.auth import get_password_hash  # noqa: E402
from app.core.clock import today_bogota  # noqa: E402
from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.liquidation_model import LiquidationModel  # noqa: E402
from app.infrastructure.models.models import UserType  # noqa: E402
from app.infrastructure.models.route_model import RouteModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_liquidations import STAMP, new_loan, new_route  # noqa: E402
from scripts.qa_reports import RESULTS, Api, check  # noqa: E402


async def new_user(kind: UserType, brand_id, label: str, *, active: bool = True) -> UserModel:
    async with async_session() as db:
        user = UserModel(id=uuid4(), username=f"qd_ra_{STAMP}_{label}", hashed_password=get_password_hash("x"), full_name=f"QD RA {label}",
                         type_user=kind, brand_id=brand_id, active=active)
        db.add(user)
        await db.commit()
        return user


async def allowed(route_id) -> list:
    async with async_session() as db:
        return list((await db.get(RouteModel, route_id)).allowed_users_ids or [])


async def main() -> int:
    api = Api()
    async with async_session() as db:
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
        sup = (await db.execute(select(UserModel).where(UserModel.username == "super_norte"))).scalars().first()
        dev = (await db.execute(select(UserModel).where(UserModel.type_user == UserType.dev))).scalars().first()
        other_brand = BrandModel(id=uuid4(), code=f"QDRA{STAMP}", name=f"QD RA {STAMP}")
        db.add(other_brand)
        await db.commit()

    collector = await new_user(UserType.collector, norte.id, "cobrador")
    partner = await new_user(UserType.partner, norte.id, "socio")
    admin = await new_user(UserType.admin, norte.id, "admin")
    inactive = await new_user(UserType.collector, norte.id, "inactivo", active=False)
    stranger = await new_user(UserType.collector, other_brand.id, "ajeno")

    route_a = await new_route([], norte.id, "RA-A")
    route_b = await new_route([collector.id], norte.id, "RA-B")
    async with async_session() as db:
        foreign_route = RouteModel(id=uuid4(), name=f"QD RA ajena {STAMP}", initial_value=0, initial_expense=0, currency="COP", opening_date=today_bogota(),
                                   brand_id=other_brand.id, allowed_users_ids=[], loans_number=0)
        db.add(foreign_route)
        await db.commit()
    a, b, uid = str(route_a.id), str(route_b.id), str(collector.id)

    print("== Permisos ==")
    for who, label in ((admin, "admin"), (collector, "cobrador"), (partner, "socio")):
        r = await api.call(who, "GET", f"/users/{uid}/routes")
        check(r.status_code == 403, f"{label} no puede ver las rutas de un usuario (403)", str(r.status_code))
        r = await api.call(who, "PUT", f"/users/{uid}/routes/{a}")
        check(r.status_code == 403, f"{label} no puede asignar (403)", str(r.status_code))
    r = await api.call(sup, "GET", f"/users/{uid}/routes")
    check(r.status_code == 200, "el super ve las rutas del usuario", r.text[:150])
    rows = {x["route_id"]: x for x in r.json()}
    check(rows[b]["assigned"] and not rows[a]["assigned"], "marca como asignadas solo las de la lista")
    check(all(x["pending_payments"] == 0 and x["open_liquidations"] == 0 for x in rows.values()), "sin cobros ni cierres, sin pendientes")
    check(str(foreign_route.id) not in rows, "no lista rutas de otras marcas")

    print("== Asignar y quitar ==")
    r = await api.call(sup, "PUT", f"/users/{uid}/routes/{a}")
    check(r.status_code == 204 and collector.id in await allowed(route_a.id), "asignar → 204 y queda en la ruta", str(r.status_code))
    r = await api.call(sup, "PUT", f"/users/{uid}/routes/{a}")
    check(r.status_code == 204 and (await allowed(route_a.id)).count(collector.id) == 1, "asignar de nuevo es idempotente (sin duplicar)")
    r = await api.call(collector, "GET", f"/routes/{a}")
    check(r.status_code == 200, "el cobrador accede a la ruta justo después de asignarla", str(r.status_code))
    listed = (await api.call(collector, "GET", "/routes/")).json()
    ids = {x["id"] for x in (listed["items"] if isinstance(listed, dict) else listed)}
    check({a, b} <= ids, "el cobrador la ve en su listado")
    r = await api.call(dev, "PUT", f"/users/{uid}/routes/{b}")
    check(r.status_code == 204, "el dev también puede asignar", str(r.status_code))
    r = await api.call(sup, "DELETE", f"/users/{uid}/routes/{a}")
    check(r.status_code == 200 and r.json() == {"removed": True, "pending_payments": 0, "open_liquidations": 0}, "quitar sin pendientes → removed", r.text[:150])
    r = await api.call(collector, "GET", f"/routes/{a}")
    check(r.status_code == 404 and collector.id not in await allowed(route_a.id), "el cobrador deja de ver la ruta (404)", str(r.status_code))
    r = await api.call(sup, "DELETE", f"/users/{uid}/routes/{a}")
    check(r.status_code == 200 and r.json()["removed"] is False, "quitar de nuevo → removed false")

    print("== Destinos inválidos ==")
    r = await api.call(sup, "PUT", f"/users/{sup.id}/routes/{a}")
    check(r.status_code == 400, "un super no se asigna (ve todas las rutas) → 400", str(r.status_code))
    r = await api.call(sup, "GET", f"/users/{dev.id}/routes")
    check(r.status_code in (400, 404), "un dev no se asigna", str(r.status_code))
    r = await api.call(sup, "PUT", f"/users/{inactive.id}/routes/{a}")
    check(r.status_code == 400, "usuario inactivo → 400", str(r.status_code))
    r = await api.call(sup, "PUT", f"/users/{stranger.id}/routes/{a}")
    check(r.status_code == 404, "usuario de otra marca → 404", str(r.status_code))
    r = await api.call(sup, "PUT", f"/users/{uid}/routes/{foreign_route.id}")
    check(r.status_code == 404, "ruta de otra marca → 404", str(r.status_code))
    r = await api.call(sup, "PUT", f"/users/{uid}/routes/{uuid4()}")
    check(r.status_code == 404, "ruta inexistente → 404", str(r.status_code))
    r = await api.call(sup, "PUT", f"/users/{uuid4()}/routes/{a}")
    check(r.status_code == 404, "usuario inexistente → 404", str(r.status_code))
    r = await api.call(dev, "PUT", f"/users/{stranger.id}/routes/{foreign_route.id}")
    check(r.status_code == 204, "el dev sí puede operar en otra marca", str(r.status_code))

    print("== Pendientes ==")
    await api.call(sup, "PUT", f"/users/{uid}/routes/{a}")
    await new_loan(api, collector, route_a, first_offset=0, value_payment=100000)
    async with async_session() as db:
        db.add(LiquidationModel(id=uuid4(), date=today_bogota(), route_id=route_a.id, collector_id=collector.id, value_base_delivered=0,
                                today_collection_goal=0, total_value_charged=0, total_value_expenses=0, value_new_loans=0))
        await db.commit()
    rows = {x["route_id"]: x for x in (await api.call(sup, "GET", f"/users/{uid}/routes")).json()}
    check(rows[a]["pending_payments"] >= 1 and rows[a]["open_liquidations"] == 1, "cuenta cobros sin liquidar y cierres abiertos", str(rows[a]))
    check(rows[b]["pending_payments"] == 0, "los pendientes son por ruta")
    r = await api.call(sup, "DELETE", f"/users/{uid}/routes/{a}")
    body = r.json()
    check(r.status_code == 200 and body["removed"] and body["pending_payments"] >= 1 and body["open_liquidations"] == 1,
          "quitar con pendientes: se quita y devuelve el aviso", r.text[:150])
    check(collector.id not in await allowed(route_a.id), "con pendientes la ruta igual queda sin el usuario")

    print("== Asignaciones simultáneas ==")
    results = await asyncio.gather(*(api.call(sup, "PUT", f"/users/{u.id}/routes/{a}") for u in (collector, partner, admin)))
    now = await allowed(route_a.id)
    check(all(x.status_code == 204 for x in results) and {collector.id, partner.id, admin.id} <= set(now) and len(now) == len(set(now)),
          "tres asignaciones a la vez no se pisan", str(now))

    print("== Validación al guardar una ruta ==")
    base = {"id": a, "name": "QD RA editada", "initial_value": 1000000, "initial_expense": 0, "opening_date": str(today_bogota())}
    keep = [str(x) for x in await allowed(route_a.id)]
    for label, extra in (("usuario de otra marca", stranger.id), ("super", sup.id), ("usuario inexistente", uuid4())):
        r = await api.call(sup, "PUT", f"/routes/{a}", json={**base, "allowed_users_ids": keep + [str(extra)]})
        check(r.status_code == 400, f"PUT /routes con {label} → 400", f"{r.status_code} {r.text[:100]}")
    r = await api.call(sup, "PUT", f"/routes/{a}", json={**base, "allowed_users_ids": keep})
    check(r.status_code == 200, "guardar la ruta con los usuarios que ya tiene → 200", r.text[:150])
    r = await api.call(sup, "PUT", f"/routes/{a}", json={**base, "allowed_users_ids": keep + [str(uid)]})
    check(r.status_code == 200, "agregar un usuario válido desde la ruta → 200", r.text[:150])

    failed = [name for ok_, name in RESULTS if not ok_]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN {len(failed)}" if failed else ""))
    for name in failed:
        print("  ✗", name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
