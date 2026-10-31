"""Resuelve UserModel a partir del subject del JWT de Clerk."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.infrastructure.clients.clerk_client import ClerkApiError, ClerkClient
from app.infrastructure.models.user_model import UserModel
from app.utils.user_credentials import clerk_username, kobros_username_candidates


async def resolve_user_by_clerk_subject(
    db: AsyncSession,
    clerk_user_id: str,
    *,
    clerk: ClerkClient | None = None,
) -> UserModel | None:
    result = await db.execute(
        select(UserModel).where(UserModel.clerk_user_id == clerk_user_id)
    )
    user = result.scalars().first()
    if user:
        return user

    clerk = clerk or ClerkClient()
    if not clerk.configured:
        return None

    try:
        clerk_user = await clerk.get_user(clerk_user_id)
    except ClerkApiError:
        return None

    clerk_login = (clerk_user.get("username") or "").strip()
    if not clerk_login:
        return None

    search_names = set(kobros_username_candidates(clerk_login))
    result = await db.execute(
        select(UserModel).where(UserModel.clerk_user_id.is_(None))
    )
    for row in result.scalars().all():
        if row.username in search_names or clerk_username(row.username) == clerk_login:
            row.clerk_user_id = clerk_user_id
            await db.commit()
            await db.refresh(row)
            return row

    return None
