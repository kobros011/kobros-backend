#!/usr/bin/env python3
"""
Crea cuentas en Clerk para usuarios Kobros sin clerk_user_id y vincula el id.

Uso (desde el contenedor api):
  python scripts/sync_users_to_clerk.py
  python scripts/sync_users_to_clerk.py --dry-run
  python scripts/sync_users_to_clerk.py --password 'Temporal123'
"""
from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.infrastructure.clients.clerk_client import ClerkClient
from app.infrastructure.dababase.db import async_session
from app.infrastructure.models.brand_model import BrandModel  # noqa: F401
from app.infrastructure.models.client_model import ClientModel  # noqa: F401
from app.infrastructure.models.client_reference_model import ClientReferenceModel  # noqa: F401
from app.infrastructure.models.client_route_model import ClientRouteModel  # noqa: F401
from app.infrastructure.models.expense_model import ExpenseModel  # noqa: F401
from app.infrastructure.models.liquidation_model import LiquidationModel  # noqa: F401
from app.infrastructure.models.loan_model import LoanModel  # noqa: F401
from app.infrastructure.models.models import UserType  # noqa: F401
from app.infrastructure.models.payment_model import PaymentModel  # noqa: F401
from app.infrastructure.models.route_model import RouteModel  # noqa: F401
from app.infrastructure.models.user_model import UserModel
from app.utils.kobros_clerk_link import link_kobros_user_to_clerk


def _generate_password() -> str:
    # Clerk mínimo 8; token_urlsafe puede traer caracteres raros — alfanumérico largo
    return secrets.token_urlsafe(12)[:16] + "Aa1"


async def sync_users(
    *,
    dry_run: bool,
    fixed_password: Optional[str],
) -> int:
    clerk = ClerkClient()
    if not clerk.configured:
        print("ERROR: CLERK_SECRET_KEY no configurada", file=sys.stderr)
        return 1

    failures = 0

    async with async_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.clerk_user_id.is_(None))
        )
        users = result.scalars().all()

        if not users:
            print("No hay usuarios pendientes de vincular con Clerk.")
            return 0

        print(f"Usuarios sin clerk_user_id: {len(users)}")

        for user in users:
            if dry_run:
                print(f"[dry-run] {user.username} ({user.id}) → vincular Clerk")
                continue

            temp_password = fixed_password or _generate_password()
            ok, msg = await link_kobros_user_to_clerk(
                user,
                clerk=clerk,
                password=temp_password,
                dry_run=False,
            )
            if ok:
                print(msg)
                if not fixed_password:
                    print(f"   contraseña temporal: {temp_password}")
            else:
                print(f"ERROR {msg}", file=sys.stderr)
                failures += 1
                continue

        if not dry_run:
            await session.commit()
            print("Cambios guardados en PostgreSQL.")

    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza usuarios Kobros con Clerk")
    parser.add_argument("--dry-run", action="store_true", help="Solo listar, sin cambios")
    parser.add_argument(
        "--password",
        help="Contraseña temporal fija para todos (mín. 8 caracteres)",
        default=None,
    )
    args = parser.parse_args()

    if args.password and len(args.password) < 8:
        print("ERROR: --password debe tener al menos 8 caracteres", file=sys.stderr)
        sys.exit(1)

    code = asyncio.run(
        sync_users(dry_run=args.dry_run, fixed_password=args.password)
    )
    sys.exit(1 if code else 0)


if __name__ == "__main__":
    main()
