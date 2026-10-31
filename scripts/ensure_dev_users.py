#!/usr/bin/env python3
"""
Bootstrap idempotente de usuarios dev (admin.carlos, admin.david) en deploy.

Ejecutar tras migraciones:
  python scripts/ensure_dev_users.py
  python scripts/ensure_dev_users.py --dry-run

Variables opcionales (recomendado en producción):
  DEV_SEED_CARLOS_PASSWORD
  DEV_SEED_DAVID_PASSWORD
Si no están definidas, se genera contraseña temporal (se imprime una vez).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.infrastructure.dababase.db import async_session
from app.infrastructure.models.brand_model import BrandModel  # noqa: F401
from app.infrastructure.models.client_model import ClientModel  # noqa: F401
from app.infrastructure.models.client_reference_model import ClientReferenceModel  # noqa: F401
from app.infrastructure.models.client_route_model import ClientRouteModel  # noqa: F401
from app.infrastructure.models.expense_model import ExpenseModel  # noqa: F401
from app.infrastructure.models.liquidation_model import LiquidationModel  # noqa: F401
from app.infrastructure.models.loan_model import LoanModel  # noqa: F401
from app.infrastructure.models.payment_model import PaymentModel  # noqa: F401
from app.infrastructure.models.route_model import RouteModel  # noqa: F401
from app.infrastructure.models.user_model import UserModel  # noqa: F401
from app.utils.dev_seed_users import ensure_dev_seed_users


def _seed_disabled() -> bool:
    return os.getenv("DEV_SEED_DISABLED", "").strip().lower() in ("1", "true", "yes")


async def run(*, dry_run: bool) -> int:
    if _seed_disabled():
        print("DEV_SEED_DISABLED: omitiendo bootstrap de usuarios dev.")
        return 0

    async with async_session() as session:
        try:
            lines = await ensure_dev_seed_users(session, dry_run=dry_run)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    for line in lines:
        print(line)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Asegura usuarios dev Carlos y David")
    parser.add_argument("--dry-run", action="store_true", help="Solo simular")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(dry_run=args.dry_run)))


if __name__ == "__main__":
    main()
