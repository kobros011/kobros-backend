"""Usuarios dev de bootstrap (Carlos, David) — idempotente en deploy."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash
from app.infrastructure.clients.clerk_client import ClerkClient
from app.infrastructure.models.models import UserType
from app.infrastructure.models.user_model import UserModel
from app.utils.kobros_clerk_link import link_kobros_user_to_clerk


@dataclass(frozen=True)
class DevSeedSpec:
    username: str
    full_name: str
    password_env: str


# Orden fijo; solo se crean los que falten en BD.
DEV_SEED_SPECS: tuple[DevSeedSpec, ...] = (
    DevSeedSpec("admin.carlos", "Carlos Garcia", "DEV_SEED_CARLOS_PASSWORD"),
    DevSeedSpec("admin.david", "David Agudelo", "DEV_SEED_DAVID_PASSWORD"),
)


def _resolve_password(spec: DevSeedSpec) -> str:
    from_env = os.getenv(spec.password_env, "").strip()
    if from_env:
        if len(from_env) < 8:
            raise ValueError(f"{spec.password_env} debe tener al menos 8 caracteres")
        return from_env
    return secrets.token_urlsafe(12)[:16] + "Aa1"


async def ensure_dev_seed_users(
    session: AsyncSession,
    *,
    clerk: Optional[ClerkClient] = None,
    dry_run: bool = False,
) -> list[str]:
    """
    Comprueba cada usuario dev; si no existe en PostgreSQL, lo crea y opcionalmente en Clerk.
    Devuelve líneas de log.
    """
    clerk = clerk or ClerkClient()
    logs: list[str] = []

    for spec in DEV_SEED_SPECS:
        existing = await session.scalar(
            select(UserModel).where(UserModel.username == spec.username)
        )
        if existing:
            logs.append(f"SKIP {spec.username} ya existe")
            if clerk.configured and not existing.clerk_user_id and not dry_run:
                password = _resolve_password(spec)
                ok, msg = await link_kobros_user_to_clerk(
                    existing, clerk=clerk, password=password, dry_run=dry_run
                )
                logs.append(msg if ok else f"WARN Clerk {spec.username}: {msg}")
                if ok and password and not os.getenv(spec.password_env):
                    logs.append(f"   contraseña temporal Clerk: {password}")
            continue

        password = _resolve_password(spec)
        if dry_run:
            logs.append(f"[dry-run] CREAR {spec.username} ({spec.full_name}) tipo dev")
            continue

        user = UserModel(
            username=spec.username,
            full_name=spec.full_name,
            type_user=UserType.dev,
            hashed_password=get_password_hash(password),
            document_id="",
        )
        session.add(user)
        await session.flush()
        logs.append(f"CREADO {spec.username} en PostgreSQL")

        if clerk.configured:
            ok, msg = await link_kobros_user_to_clerk(
                user, clerk=clerk, password=password, dry_run=False
            )
            logs.append(msg if ok else f"ERROR Clerk {spec.username}: {msg}")
        else:
            logs.append(f"INFO {spec.username}: sin CLERK_SECRET_KEY, solo BD")

        if not os.getenv(spec.password_env):
            logs.append(f"   contraseña inicial: {password}")

    if not dry_run:
        await session.commit()

    return logs
