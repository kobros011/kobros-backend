"""Reglas de la moneda de una ruta: sale de las monedas de su marca y no cambia si la ruta ya tiene movimiento."""
from typing import Optional
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currencies import is_valid
from app.core.exceptions import BadRequestException, ConflictException
from app.infrastructure.models.brand_settings_model import BrandSettingsModel
from app.infrastructure.models.client_route_model import ClientRouteModel
from app.infrastructure.models.expense_model import ExpenseModel
from app.infrastructure.models.liquidation_model import LiquidationModel
from app.infrastructure.models.loan_model import LoanModel
from app.infrastructure.models.route_movement_model import RouteMovementModel


async def brand_currencies(db: AsyncSession, brand_id: UUID) -> list[str]:
    row = (await db.execute(select(BrandSettingsModel.currencies).where(BrandSettingsModel.brand_id == brand_id))).first()
    return list(row[0] or []) if row else []


async def resolve_new_route_currency(db: AsyncSession, brand_id: UUID, requested: Optional[str]) -> str:
    """Moneda de una ruta nueva: la pedida (válida para la marca), o la única de la marca si no pidió ninguna."""
    allowed = await brand_currencies(db, brand_id)
    if not allowed:
        raise BadRequestException("La marca no tiene monedas configuradas. Configúralas en Configuración antes de crear rutas")
    if requested is None:
        if len(allowed) == 1:
            return allowed[0]
        raise BadRequestException("Elige la moneda de la ruta")
    return validate_route_currency(requested, allowed)


def validate_route_currency(code: str, allowed: list[str]) -> str:
    code = code.strip().upper()
    if not is_valid(code):
        raise BadRequestException(f"Moneda no válida: {code}")
    if code not in allowed:
        raise BadRequestException(f"La marca no usa la moneda {code}")
    return code


async def route_has_data(db: AsyncSession, route_id: UUID) -> bool:
    """Créditos (y por tanto pagos), gastos, liquidaciones o movimientos de caja, activos o no."""
    checks = (
        exists().where(LoanModel.clientroute_id == ClientRouteModel.id, ClientRouteModel.route_id == route_id),
        exists().where(ExpenseModel.route_id == route_id),
        exists().where(LiquidationModel.route_id == route_id),
        exists().where(RouteMovementModel.route_id == route_id),
    )
    for check in checks:
        if (await db.execute(select(check))).scalar():
            return True
    return False


async def ensure_can_change_currency(db: AsyncSession, route_id: UUID) -> None:
    if await route_has_data(db, route_id):
        raise ConflictException("No puedes cambiar la moneda de una ruta que ya tiene créditos, gastos, liquidaciones o movimientos")
