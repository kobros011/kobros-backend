"""Validación de los usuarios que se asignan a una ruta (`allowed_users_ids`)."""
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.infrastructure.models.user_model import UserModel

ASSIGNABLE_ROLES = ("03", "04", "05")  # admin, socio, cobrador


async def validate_new_route_users(db: AsyncSession, brand_id: UUID, new_ids: Iterable[UUID], current_ids: Iterable[UUID] = ()) -> None:
    """Los usuarios que se **agregan** deben existir, ser de la marca de la ruta y de un rol asignable.

    Los que ya estaban no se revalidan: así editar otros datos de la ruta no falla por asignaciones históricas.
    """
    added = set(new_ids) - set(current_ids)
    if not added:
        return
    users = {u.id: u for u in (await db.execute(select(UserModel).where(UserModel.id.in_(added)))).scalars().all()}
    for user_id in added:
        user = users.get(user_id)
        role = getattr(user.type_user, "value", str(user.type_user)) if user else None
        if user is None or user.brand_id != brand_id or role not in ASSIGNABLE_ROLES:
            raise BadRequestException("Solo se pueden asignar administradores, socios y cobradores de la marca de la ruta")
