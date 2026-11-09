#!/usr/bin/env python3
"""
QA de fiadores y referencias como contactos del cliente (`contacts` en POST/PUT /clients/). No borra nada (datos "QD CT").

Comprueba: crear con varios de cada tipo, orden (fiadores primero) y principal = primero de cada tipo, validaciones (nombre o
celular vacíos, tipo inválido, tope), editar reemplaza la lista y `contacts` ausente no la toca, quitar todos, lectura por id y
más_info, permisos (cobrador sin la ruta, otra marca) y que ya no existen los campos viejos (`guarantor_*`, `references`).

Uso (contenedor api):  python scripts/qa_client_contacts.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

import app.main  # noqa: E402,F401
from app.infrastructure.dababase.db import async_session  # noqa: E402
from app.infrastructure.models.brand_model import BrandModel  # noqa: E402
from app.infrastructure.models.client_contact_model import ClientContactModel  # noqa: E402
from app.infrastructure.models.user_model import UserModel  # noqa: E402
from scripts.qa_liquidations import STAMP, new_route  # noqa: E402
from scripts.qa_reports import RESULTS, Api, check  # noqa: E402

COUNTER = {"n": 0}
BRAND: dict = {}


def contact(kind: str, name: str, phone: str = "3001112233", address: str | None = "Calle QA") -> dict:
    return {"kind": kind, "name": name, "phone": phone, "address": address}


def body(route_id, contacts, label: str) -> dict:
    COUNTER["n"] += 1
    tag = f"{STAMP}{COUNTER['n']:02d}"
    out = {
        "full_name": f"QD CT {label} {tag}", "id_document": f"QD-CT{tag}", "current_address": "Calle QA", "current_phone": "3000000000",
        "current_mobile": "3000000000", "neighborhood": "QA", "linking_date": datetime.now().isoformat(), "routes": [{"route_id": str(route_id)}],
        "brand_id": BRAND["id"],
    }
    if contacts is not None:
        out["contacts"] = contacts
    return out


async def db_count(client_id) -> int:
    async with async_session() as db:
        return (await db.execute(select(func.count()).select_from(ClientContactModel).where(ClientContactModel.client_id == client_id))).scalar_one()


def summary(client: dict) -> list[tuple]:
    return [(c["kind"], c["name"], c["position"], c["is_primary"]) for c in client["contacts"]]


async def main() -> int:
    api = Api()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
    BRAND["id"] = str(norte.id)
    sup, carlos = users["super_norte"], users["qd_carlos"]
    outsider = next((u for u in users.values() if u.brand_id and u.brand_id != norte.id and u.type_user.value in ("02", "03")), None)

    route = await new_route([carlos.id], norte.id, "CT-A")
    other_route = await new_route([users["super_norte"].id], norte.id, "CT-X")
    rid = str(route.id)

    print("== Crear ==")
    r = await api.call(sup, "POST", "/clients/", json=body(rid, None, "sin"))
    check(r.status_code == 201 and r.json()["contacts"] == [], "sin contactos → 201 y lista vacía", r.text[:150])

    mixed = [contact("referencia", "Ref Uno"), contact("fiador", "Fiador Uno"), contact("referencia", "Ref Dos"), contact("fiador", "Fiador Dos", address=None)]
    r = await api.call(sup, "POST", "/clients/", json=body(rid, mixed, "mixto"))
    check(r.status_code == 201, "2 fiadores + 2 referencias → 201 (sin tope de 2)", r.text[:200])
    client = r.json()
    check(summary(client) == [("fiador", "Fiador Uno", 1, True), ("fiador", "Fiador Dos", 2, False), ("referencia", "Ref Uno", 1, True), ("referencia", "Ref Dos", 2, False)],
          "fiadores primero y principal = primero de cada tipo", str(summary(client)))
    check(client["contacts"][1]["address"] is None, "la dirección es opcional")

    many = [contact("referencia", f"Ref {i}") for i in range(5)]
    r = await api.call(sup, "POST", "/clients/", json=body(rid, many, "cinco"))
    check(r.status_code == 201 and len(r.json()["contacts"]) == 5, "5 referencias → 201")

    print("== Validaciones ==")
    for label, payload in (
        ("nombre vacío", contact("fiador", "  ")),
        ("celular vacío", contact("referencia", "Ana", phone="")),
        ("celular solo espacios", contact("referencia", "Ana", phone="   ")),
        ("tipo inválido", {"kind": "aval", "name": "Ana", "phone": "300"}),
    ):
        r = await api.call(sup, "POST", "/clients/", json=body(rid, [payload], "val"))
        check(r.status_code == 422, f"{label} → 422", str(r.status_code))
    r = await api.call(sup, "POST", "/clients/", json=body(rid, [contact("referencia", f"R{i}") for i in range(21)], "tope"))
    check(r.status_code == 422, "más de 20 contactos → 422", str(r.status_code))
    r = await api.call(sup, "POST", "/clients/", json={**body(rid, None, "viejo"), "guarantor_name": "X", "references": [{"name": "Y"}]})
    check(r.status_code == 201 and r.json()["contacts"] == [], "los campos viejos (guarantor_*, references) se ignoran")

    print("== Editar ==")
    cid = client["id"]
    r = await api.call(sup, "PUT", f"/clients/{cid}", json={"id": cid, "full_name": client["full_name"], "contacts": [contact("referencia", "Solo Ref")]})
    check(r.status_code == 200 and summary(r.json()) == [("referencia", "Solo Ref", 1, True)], "editar reemplaza la lista completa", r.text[:200])
    r = await api.call(sup, "PUT", f"/clients/{cid}", json={"id": cid, "full_name": client["full_name"] + " b"})
    check(r.status_code == 200 and len(r.json()["contacts"]) == 1, "sin `contacts` en el PUT no se tocan", r.text[:200])
    r = await api.call(sup, "PUT", f"/clients/{cid}", json={"id": cid, "contacts": [contact("fiador", "Nuevo Fiador"), contact("fiador", "Otro Fiador"), contact("referencia", "Solo Ref")]})
    check(r.status_code == 200 and [c["name"] for c in r.json()["contacts"]] == ["Nuevo Fiador", "Otro Fiador", "Solo Ref"], "agregar más de un fiador", r.text[:200])
    r = await api.call(sup, "PUT", f"/clients/{cid}", json={"id": cid, "contacts": [{**contact("fiador", ""), "name": ""}]})
    check(r.status_code == 422 and await db_count(cid) == 3, "PUT inválido → 422 y no cambia nada")
    r = await api.call(sup, "PUT", f"/clients/{cid}", json={"id": cid, "contacts": []})
    check(r.status_code == 200 and r.json()["contacts"] == [] and await db_count(cid) == 0, "lista vacía quita todos los contactos")

    print("== Lectura ==")
    r = await api.call(sup, "POST", "/clients/", json=body(rid, [contact("fiador", "Leer Fiador"), contact("referencia", "Leer Ref")], "lee"))
    got = r.json()
    one = (await api.call(sup, "GET", f"/clients/{got['id']}")).json()
    info = (await api.call(sup, "GET", f"/clients/{got['id']}/more_info/", params={"route_id": rid})).json()
    check(summary(one) == summary(got) == summary(info) and len(one["contacts"]) == 2, "GET por id y more_info traen los contactos")
    listed = (await api.call(sup, "GET", "/clients/", params={"route_id": rid})).json()
    items = listed["items"] if isinstance(listed, dict) else listed
    check(any(c["id"] == got["id"] and len(c["contacts"]) == 2 for c in items), "el listado trae los contactos")

    print("== Permisos ==")
    r = await api.call(carlos, "POST", "/clients/", json=body(rid, [contact("fiador", "Del cobrador")], "cobrador"))
    check(r.status_code == 201 and len(r.json()["contacts"]) == 1, "el cobrador crea con contactos en su ruta", r.text[:150])
    r = await api.call(carlos, "POST", "/clients/", json=body(other_route.id, [contact("fiador", "Ajena")], "ajena"))
    check(r.status_code in (403, 404), "el cobrador no puede usar una ruta que no tiene", str(r.status_code))
    if outsider:
        r = await api.call(outsider, "PUT", f"/clients/{got['id']}", json={"id": got["id"], "contacts": [contact("fiador", "Intruso")]})
        check(r.status_code in (403, 404) and await db_count(got["id"]) == 2, "otra marca no puede editar los contactos", str(r.status_code))

    failed = [name for ok_, name in RESULTS if not ok_]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN {len(failed)}" if failed else ""))
    for name in failed:
        print("  ✗", name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
