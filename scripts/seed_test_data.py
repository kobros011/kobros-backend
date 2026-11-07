#!/usr/bin/env python3
"""
Seed de datos de prueba para validar el feature "Usuarios del Super Usuario"
(ocultar Marcas para rol 02, listado configurable, cambio de contraseña,
autorización por marca).

Idempotente: si un registro ya existe (por `code` de marca o `username` de
usuario) lo reutiliza en vez de duplicarlo.

Uso (desde el contenedor api):
  python scripts/seed_test_data.py
  python scripts/seed_test_data.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.infrastructure.clients.clerk_client import ClerkClient
from app.infrastructure.dababase.db import async_session
from app.infrastructure.models.brand_model import BrandModel
from app.infrastructure.models.client_model import ClientModel  # noqa: F401
from app.infrastructure.models.client_reference_model import ClientReferenceModel  # noqa: F401
from app.infrastructure.models.client_route_model import ClientRouteModel  # noqa: F401
from app.infrastructure.models.expense_model import ExpenseModel  # noqa: F401
from app.infrastructure.models.liquidation_model import LiquidationModel  # noqa: F401
from app.infrastructure.models.loan_model import LoanModel  # noqa: F401
from app.infrastructure.models.models import UserType
from app.infrastructure.models.payment_model import PaymentModel  # noqa: F401
from app.infrastructure.models.route_model import RouteModel  # noqa: F401
from app.infrastructure.models.user_model import UserModel
from app.utils.kobros_clerk_link import link_kobros_user_to_clerk

TEST_PASSWORD = os.getenv("SEED_TEST_PASSWORD", "KobrosTest123")


@dataclass(frozen=True)
class BrandSpec:
    name: str
    code: str


@dataclass(frozen=True)
class UserSpec:
    username: str
    full_name: str
    type_user: UserType
    email: str
    brand_code: str | None  # None = sin marca (dev-like / super global)


BRANDS: tuple[BrandSpec, ...] = (
    BrandSpec("Marca Norte", "NORTE01"),
    BrandSpec("Marca Sur", "SUR01"),
)

USERS: tuple[UserSpec, ...] = (
    # Super global (brand_id NULL): debe ver todas las marcas/usuarios igual que dev.
    UserSpec("super.global", "Super Global (QA)", UserType.super, "super.global.qa@kobros-demo.com", None),
    # Super con marca propia: para validar que Marcas se oculta en el front
    # y que el backend lo limita a su propia marca.
    UserSpec("super.norte", "Super Norte (QA)", UserType.super, "super.norte.qa@kobros-demo.com", "NORTE01"),
    # Admin de otra marca: para probar que super.norte NO puede ver/editar
    # este usuario (403/404 por marca).
    UserSpec("admin.sur", "Admin Sur (QA)", UserType.admin, "admin.sur.qa@kobros-demo.com", "SUR01"),
    # Admin de la marca Norte: para probar que super.norte SÍ puede gestionarlo.
    UserSpec("admin.norte", "Admin Norte (QA)", UserType.admin, "admin.norte.qa@kobros-demo.com", "NORTE01"),
)


async def ensure_brand(session, spec: BrandSpec, *, dry_run: bool) -> BrandModel | None:
    existing = await session.scalar(select(BrandModel).where(BrandModel.code == spec.code))
    if existing:
        print(f"SKIP marca {spec.code} ya existe ({existing.id})")
        return existing

    if dry_run:
        print(f"[dry-run] CREAR marca {spec.code} ({spec.name})")
        return None

    brand = BrandModel(name=spec.name, code=spec.code, routes_available=5)
    session.add(brand)
    await session.flush()
    print(f"CREADA marca {spec.code} ({brand.id})")
    return brand


async def ensure_user(
    session,
    spec: UserSpec,
    brands_by_code: dict[str, BrandModel],
    *,
    clerk: ClerkClient,
    dry_run: bool,
) -> None:
    existing = await session.scalar(select(UserModel).where(UserModel.username == spec.username))
    brand = brands_by_code.get(spec.brand_code) if spec.brand_code else None

    if existing:
        print(f"SKIP {spec.username} ya existe ({existing.id})")
        if not existing.clerk_user_id and clerk.configured and not dry_run:
            ok, msg = await link_kobros_user_to_clerk(existing, clerk=clerk, password=TEST_PASSWORD)
            print(("OK " if ok else "WARN ") + f"Clerk {spec.username}: {msg}")
            await session.commit()
        return

    if dry_run:
        print(f"[dry-run] CREAR {spec.username} ({spec.type_user.value}, marca={spec.brand_code})")
        return

    user = UserModel(
        username=spec.username,
        full_name=spec.full_name,
        email=spec.email,
        type_user=spec.type_user,
        document_id="",
        brand_id=brand.id if brand else None,
        hashed_password="",  # se setea abajo al vincular con Clerk
    )
    session.add(user)
    await session.flush()

    if clerk.configured:
        ok, msg = await link_kobros_user_to_clerk(user, clerk=clerk, password=TEST_PASSWORD)
        print(("OK " if ok else "WARN ") + f"Clerk {spec.username}: {msg}")
    else:
        user.hashed_password = ""
        print(f"INFO {spec.username}: sin CLERK_SECRET_KEY, solo BD (sin login real)")

    await session.commit()
    print(f"CREADO {spec.username} ({user.id}) tipo={spec.type_user.value} marca={spec.brand_code}")


async def run(*, dry_run: bool) -> int:
    clerk = ClerkClient()
    async with async_session() as session:
        brands_by_code: dict[str, BrandModel] = {}
        for spec in BRANDS:
            brand = await ensure_brand(session, spec, dry_run=dry_run)
            if brand:
                brands_by_code[spec.code] = brand
        if not dry_run:
            await session.commit()

        for spec in USERS:
            await ensure_user(session, spec, brands_by_code, clerk=clerk, dry_run=dry_run)

    print("\nListo. Credenciales de prueba (todas comparten la misma contraseña):")
    print(f"  contraseña: {TEST_PASSWORD}")
    for spec in USERS:
        print(f"  - {spec.username} / {spec.email}  [{spec.type_user.value}]  marca={spec.brand_code or '(ninguna)'}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed de marcas y usuarios de prueba")
    parser.add_argument("--dry-run", action="store_true", help="Solo simular")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(dry_run=args.dry_run)))


if __name__ == "__main__":
    main()
