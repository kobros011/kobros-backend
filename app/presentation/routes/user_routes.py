import os
from typing import Optional, Union

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID

from app.core.pagination import (
    Page,
    PaginationParams,
    filters_from_request,
    optional_pagination_params,
    page_or_list,
)
from app.infrastructure.clients.clerk_client import ClerkApiError, ClerkClient
from app.infrastructure.dababase.db import get_db
from app.infrastructure.models.user_model import UserModel
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.utils.require_authentication import require_authentication
from app.infrastructure.utils.require_role import require_role
from app.presentation.shemas.user_shema import (
    UserCreate,
    UserPasswordUpdate,
    UserRead,
    UserUpdate,
    user_to_read,
)
from app.use_cases.user_cases import UserUseCases
from app.utils.user_credentials import normalize_email

router = APIRouter(dependencies=[Depends(require_authentication)])

_ADMIN_ROLES = ("01", "02", "03")  # dev, super, admin
_SUPER_ROLES = ("01", "02")        # dev, super


def get_clerk_client() -> ClerkClient:
    return ClerkClient()


def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_user_usecases(
    user: UserModel = Depends(require_authentication),
    repository: UserRepository = Depends(get_user_repository),
    clerk: ClerkClient = Depends(get_clerk_client),
) -> UserUseCases:
    usecases = UserUseCases(repository=repository, clerk_client=clerk)
    usecases.user = user
    repository.user = user
    return usecases


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    _: UserModel = Depends(require_role(*_ADMIN_ROLES)),
    usecases: UserUseCases = Depends(get_user_usecases),
):
    created = await usecases.create_user(user=user_in)
    return user_to_read(created)


@router.get("/", response_model=Union[Page[UserRead], list[UserRead]])
async def list_users(
    request: Request,
    pagination: Optional[PaginationParams] = Depends(optional_pagination_params),
    usecases: UserUseCases = Depends(get_user_usecases),
):
    users, total = await usecases.list_users(filters_from_request(request), pagination)
    return page_or_list([user_to_read(u) for u in users if u], total, pagination)


@router.get("/{user_id}", response_model=UserRead)
async def read_user(user_id: UUID, usecases: UserUseCases = Depends(get_user_usecases)):
    user = await usecases.get_user(user_id)
    return user_to_read(user)


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_in: UserUpdate,
    _: UserModel = Depends(require_role(*_ADMIN_ROLES)),
    usecases: UserUseCases = Depends(get_user_usecases),
):
    updated = await usecases.update_user(user=user_in)
    return user_to_read(updated)


@router.put("/{user_id}/toggle")
async def toggle_user(
    user_id: UUID,
    _: UserModel = Depends(require_role(*_ADMIN_ROLES)),
    usecases: UserUseCases = Depends(get_user_usecases),
):
    return await usecases.toggle_user(user_id)


@router.put("/{user_id}/password", response_model=UserRead)
async def set_user_password(
    user_id: UUID,
    body: UserPasswordUpdate,
    _: UserModel = Depends(require_role(*_SUPER_ROLES)),
    usecases: UserUseCases = Depends(get_user_usecases),
):
    updated = await usecases.set_password(user_id, body.password)
    return user_to_read(updated)


@router.post("/{user_id}/send-password-reset")
async def send_password_reset(
    user_id: UUID,
    actor: UserModel = Depends(require_role(*_SUPER_ROLES)),
    db: AsyncSession = Depends(get_db),
    clerk: ClerkClient = Depends(get_clerk_client),
):
    clerk_secret = os.getenv("CLERK_SECRET_KEY", "")
    if not clerk_secret:
        raise HTTPException(status_code=500, detail="CLERK_SECRET_KEY no configurada")

    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    target = result.scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if actor.brand_id and target.brand_id != actor.brand_id:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not target.clerk_user_id:
        raise HTTPException(status_code=400, detail="El usuario no tiene cuenta Clerk vinculada")
    if not normalize_email(target.email):
        raise HTTPException(
            status_code=400,
            detail="El usuario no tiene correo; asigne la contraseña manualmente",
        )

    try:
        await clerk.send_password_reset_email(target.clerk_user_id)
    except ClerkApiError as exc:
        status_code = 502 if exc.status_code >= 500 else 400
        raise HTTPException(status_code=status_code, detail=exc.message) from exc

    return {"sent": True}
