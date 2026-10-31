"""Vincula un UserModel de Kobros con Clerk (crear o enlazar por username)."""
from __future__ import annotations

from typing import Optional

from app.core.auth import get_password_hash
from app.infrastructure.clients.clerk_client import ClerkApiError, ClerkClient
from app.infrastructure.models.user_model import UserModel
from app.utils.user_credentials import clerk_username, normalize_email


def _type_user_code(type_user) -> str:
    if hasattr(type_user, "value"):
        return type_user.value
    return str(type_user)


async def link_kobros_user_to_clerk(
    user: UserModel,
    *,
    clerk: ClerkClient,
    password: str,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """
    Crea o enlaza la cuenta en Clerk y actualiza clerk_user_id / hash en el modelo.
    Devuelve (ok, mensaje para logs).
    """
    safe_username = clerk_username(user.username)
    renamed = safe_username != user.username
    type_code = _type_user_code(user.type_user)
    email = normalize_email(user.email)
    full_name = user.full_name or user.username
    label = user.username

    if dry_run:
        return True, f"[dry-run] {label} → Clerk ({safe_username})"

    clerk_id: Optional[str] = None
    linked_existing = False
    try:
        created = await clerk.create_user(
            username=safe_username,
            password=password,
            full_name=full_name,
            type_user_code=type_code,
            email=email,
        )
        clerk_id = created.get("id")
    except ClerkApiError as exc:
        try:
            existing = await clerk.find_user_by_username(safe_username)
        except ClerkApiError:
            existing = None
        if existing and existing.get("id"):
            clerk_id = existing["id"]
            linked_existing = True
            try:
                await clerk.update_user(
                    clerk_id,
                    password=password,
                    type_user_code=type_code,
                )
                if email:
                    await clerk.sync_email(clerk_id, email)
            except ClerkApiError as link_exc:
                return False, f"{label}: {link_exc.message}"
        else:
            return False, f"{label}: {exc.message}"

    if not clerk_id:
        return False, f"{label}: Clerk no devolvió id"

    if renamed:
        user.username = safe_username

    user.clerk_user_id = clerk_id
    user.hashed_password = get_password_hash(password)
    if not user.full_name:
        user.full_name = full_name

    action = "vinculado" if linked_existing else "creado"
    return True, f"OK ({action}) {label} → {clerk_id}"
