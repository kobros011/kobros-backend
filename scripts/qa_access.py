#!/usr/bin/env python3
"""
QA de alcance por id: crédito y pago pedidos por su id respetan marca, rol y ruta asignada.

Crea una ruta nueva con un crédito y prueba, con usuarios reales de la BD, que:
  * el super de la marca y el cobrador asignado SÍ acceden;
  * un usuario de OTRA marca y un cobrador NO asignado reciben 404 (no se revela que existe);
  * el cobrador no puede editar ni eliminar créditos (403);
  * listar pagos sin `loan_id` se rechaza (antes devolvía los de todas las marcas).
No borra nada (datos QD Liq).

Uso (contenedor api):  python scripts/qa_access.py
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


async def main() -> int:
    api = Api()
    async with async_session() as db:
        users = {u.username: u for u in (await db.execute(select(UserModel))).scalars().all()}
        norte = (await db.execute(select(BrandModel).where(BrandModel.code == "NORTE01"))).scalars().first()
    sup, carlos, julian = users["super_norte"], users["qd_carlos"], users["qd_julian"]
    outsider = next((u for u in users.values() if u.brand_id and u.brand_id != norte.id and u.type_user.value in ("02", "03")), None)

    route = await new_route([carlos.id], norte.id, "ACC")           # carlos asignado, julian NO
    loan = await new_loan(api, sup, route, first_offset=0)
    q = (await api.call(sup, "GET", "/payments/history", params={"loan_id": loan["id"]})).json()["items"][0]

    print("== Crédito por id ==")
    check((await api.call(sup, "GET", f"/loans/{loan['id']}")).status_code == 200, "el super de la marca lee el crédito (200)")
    check((await api.call(carlos, "GET", f"/loans/{loan['id']}")).status_code == 200, "el cobrador asignado lee el crédito (200)")
    check((await api.call(julian, "GET", f"/loans/{loan['id']}")).status_code == 404, "un cobrador NO asignado a la ruta no lo ve (404)")
    if outsider:
        check((await api.call(outsider, "GET", f"/loans/{loan['id']}")).status_code == 404, f"un usuario de otra marca ({outsider.username}) no lo ve (404)")
        r = await api.call(outsider, "DELETE", f"/loans/{loan['id']}")
        check(r.status_code == 404, "otra marca no puede eliminarlo (404)", str(r.status_code))
    check((await api.call(carlos, "DELETE", f"/loans/{loan['id']}")).status_code == 403, "un cobrador no puede eliminar créditos (403)")
    body = {"id": loan["id"], "loan_number": loan["loan_number"], "initial_date": loan["initial_date"], "end_date": loan["end_date"],
            "value_quota_fixed": 1, "agreed_quotas": loan["agreed_quotas"], "date_first_quota": loan["date_first_quota"], "payment_method": loan["payment_method"],
            "value_capital": 1, "value_utility_loan": 0, "value_total_loan": 1, "interest_rate": 0, "clientroute_id": loan["clientroute_id"]}
    check((await api.call(carlos, "PUT", f"/loans/{loan['id']}", json=body)).status_code == 403, "un cobrador no puede editar créditos (403)")
    if outsider:
        check((await api.call(outsider, "PUT", f"/loans/{loan['id']}", json=body)).status_code == 404, "otra marca no puede editarlo (404)")
    still = (await api.call(sup, "GET", f"/loans/{loan['id']}")).json()
    check(abs(still["value_total_loan"] - 600000) <= 0.01, "el crédito sigue intacto tras los intentos rechazados (total $600.000)")

    print("== Pago por id ==")
    check((await api.call(sup, "GET", f"/payments/{q['id']}")).status_code == 200, "el super lee el pago (200)")
    check((await api.call(julian, "GET", f"/payments/{q['id']}")).status_code == 404, "cobrador no asignado: no ve el pago (404)")
    check((await api.call(julian, "PUT", f"/payments/{q['id']}/pay", params={"value": 100000})).status_code == 404, "cobrador no asignado: no puede cobrar el pago (404)")
    if outsider:
        check((await api.call(outsider, "PUT", f"/payments/{q['id']}/pay", params={"value": 100000})).status_code == 404, "otra marca: no puede cobrar el pago (404)")
    untouched = await api.call(sup, "GET", "/payments/history", params={"loan_id": loan["id"]})
    check(untouched.json()["summary"]["total_paid"] == 0, "los intentos rechazados no movieron dinero (pagado = 0)")
    check((await api.call(carlos, "PUT", f"/payments/{q['id']}/pay", params={"value": 100000})).status_code == 200, "el cobrador asignado sí cobra (200)")

    print("== Pagos de un crédito ==")
    check((await api.call(sup, "GET", "/payments/")).status_code == 400, "listar pagos sin loan_id se rechaza (400)")
    check((await api.call(sup, "GET", "/payments/", params={"loan_id": loan["id"]})).status_code == 200, "listar pagos de un crédito propio (200)")
    check((await api.call(julian, "GET", "/payments/", params={"loan_id": loan["id"]})).status_code == 404, "cobrador no asignado: no lista sus pagos (404)")
    if outsider:
        check((await api.call(outsider, "GET", "/payments/", params={"loan_id": loan["id"]})).status_code == 404, "otra marca: no lista sus pagos (404)")

    failed = [name for ok, name in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} verificaciones OK" + (f" — FALLAN: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
