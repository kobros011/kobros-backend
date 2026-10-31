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

from app.core.auth import get_password_hash
from app.infrastructure.clients.clerk_client import ClerkApiError, ClerkClient
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
from app.utils.user_credentials import clerk_username, normalize_email


def _type_user_code(type_user) -> str:
    if hasattr(type_user, "value"):
        return type_user.value
    return str(type_user)


def _generate_password() -> str:
    # Clerk mínimo 8; token_urlsafe puede traer caracteres raros — alfanumérico largo
    return secrets.token_urlsafe(12)[:16] + "Aa1"


async def _find_clerk_by_username(clerk: ClerkClient, username: str) -> Optional[dict]:
    try:
        return await clerk.find_user_by_username(username)
    except ClerkApiError:
        return None


def _clerk_username(username: str) -> tuple[str, bool]:
    """Clerk por defecto no acepta '.'; normaliza a '_' si hace falta."""
    safe = clerk_username(username)
    return safe, safe != username


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
            clerk_username, renamed = _clerk_username(user.username)
            label = f"{user.username} ({user.id})"
            if renamed:
                label += f" → clerk/kobros: {clerk_username}"
            temp_password = fixed_password or _generate_password()
            type_code = _type_user_code(user.type_user)
            email = normalize_email(user.email)
            full_name = user.full_name or user.username

            if dry_run:
                print(f"[dry-run] {label} → crear en Clerk (tipo {type_code})")
                continue

            clerk_id: Optional[str] = None
            linked_existing = False
            try:
                created = await clerk.create_user(
                    username=clerk_username,
                    password=temp_password,
                    full_name=full_name,
                    type_user_code=type_code,
                    email=email,
                )
                clerk_id = created.get("id")
            except ClerkApiError as exc:
                existing = await _find_clerk_by_username(clerk, clerk_username)
                if existing and existing.get("id"):
                    clerk_id = existing["id"]
                    linked_existing = True
                    try:
                        await clerk.update_user(
                            clerk_id,
                            password=temp_password,
                            type_user_code=type_code,
                        )
                        if email:
                            await clerk.sync_email(clerk_id, email)
                    except ClerkApiError as link_exc:
                        print(f"ERROR {label}: {link_exc.message}", file=sys.stderr)
                        failures += 1
                        continue
                else:
                    print(f"ERROR {label}: {exc.message}", file=sys.stderr)
                    failures += 1
                    continue

            if not clerk_id:
                print(f"ERROR {label}: Clerk no devolvió id", file=sys.stderr)
                failures += 1
                continue

            if renamed:
                user.username = clerk_username

            user.clerk_user_id = clerk_id
            user.hashed_password = get_password_hash(temp_password)
            if not user.full_name:
                user.full_name = full_name

            if not user.active:
                try:
                    await clerk.ban_user(clerk_id)
                except ClerkApiError:
                    pass

            action = "vinculado" if linked_existing else "creado"
            print(f"OK ({action}) {label} → {clerk_id}")
            print(f"   contraseña temporal: {temp_password}")

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
