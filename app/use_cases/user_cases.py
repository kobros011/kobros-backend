from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException

from app.core.auth import get_password_hash
from app.domain.entities.user import User
from app.domain.repositories.user_repository import AbstractUserRepository
from app.infrastructure.clients.clerk_client import ClerkApiError, ClerkClient
from app.infrastructure.models.user_model import UserModel
from app.infrastructure.models.models import UserType
from app.presentation.shemas.user_shema import UserCreate, UserFilters, UserUpdate
from app.utils.user_credentials import clerk_username, normalize_email


def _type_user_code(enum_val) -> str:
    if hasattr(enum_val, "value"):
        return enum_val.value
    return str(enum_val)


class UserUseCases:
    user: Optional[UserModel] = None

    def __init__(self, repository: AbstractUserRepository, clerk_client: Optional[ClerkClient] = None):
        self.repository = repository
        self.clerk = clerk_client or ClerkClient()

    async def get_user(self, user_id: UUID) -> Optional[User]:
        user = await self.repository.get_user_by_id(user_id)
        self._ensure_same_brand(user)
        return user

    async def list_users(self, filters: UserFilters) -> List[Optional[User]]:
        return await self.repository.list_users(filters)

    async def create_user(self, user: UserCreate) -> User:
        email = normalize_email(user.email)
        user_data = user.model_dump(exclude=["password"])
        user_data["email"] = email
        user_data["type_user"] = UserType[UserType.get_type(user_type=user.type_user)]

        clerk_user_id = None
        try:
            clerk_resp = await self.clerk.create_user(
                username=clerk_username(user.username),
                password=user.password,
                full_name=user.full_name,
                type_user_code=user.type_user,
                email=email,
            )
            clerk_user_id = clerk_resp["id"]
        except ClerkApiError as exc:
            status = 502 if exc.status_code >= 500 else 400
            raise HTTPException(status_code=status, detail=exc.message) from exc

        new_user = User(
            **user_data,
            hashed_password=get_password_hash(user.password),
            clerk_user_id=clerk_user_id,
        )
        try:
            return await self.repository.create_user(new_user)
        except Exception:
            if clerk_user_id:
                try:
                    await self.clerk.delete_user(clerk_user_id)
                except ClerkApiError:
                    pass
            raise

    async def update_user(self, user: UserUpdate) -> User:
        existing = await self.repository.get_user_by_id(user.id)
        self._ensure_same_brand(existing)
        type_user_code = user.type_user
        email = normalize_email(user.email)

        # Only a dev (no brand) may reassign a user's brand; others keep the
        # user's current brand regardless of what was sent in the body.
        actor_is_dev = bool(self.user) and self.user.brand_id is None
        new_brand_id = user.brand_id if actor_is_dev else existing.brand_id

        user.type_user = UserType.get_type(user_type=user.type_user)

        if existing.clerk_user_id:
            try:
                await self.clerk.update_user(
                    existing.clerk_user_id,
                    username=clerk_username(user.username),
                    type_user_code=type_user_code,
                )
                if (existing.email or None) != (email or None):
                    await self.clerk.sync_email(existing.clerk_user_id, email)
            except ClerkApiError as exc:
                status = 502 if exc.status_code >= 500 else 400
                raise HTTPException(status_code=status, detail=exc.message) from exc

        payload = user.model_dump(exclude_unset=True)
        payload["email"] = email
        payload["type_user"] = type_user_code
        payload["brand_id"] = new_brand_id
        return await self.repository.update_user(UserUpdate(**payload))

    async def update_password(self, uuid: UUID, password: str):
        new_password = get_password_hash(password)
        return await self.repository.update_password(uuid, new_password)

    def _ensure_same_brand(self, target: User) -> None:
        """A brand-scoped actor (super/admin) may only act on users of their
        own brand. A dev (brand_id is None) may act on anyone."""
        if self.user and self.user.brand_id and target.brand_id != self.user.brand_id:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

    async def set_password(self, user_id: UUID, password: str) -> User:
        user = await self.repository.get_user_by_id(user_id)
        self._ensure_same_brand(user)
        type_code = _type_user_code(user.type_user)

        if not user.clerk_user_id:
            try:
                clerk_resp = await self.clerk.create_user(
                    username=clerk_username(user.username),
                    password=password,
                    full_name=user.full_name or user.username,
                    type_user_code=type_code,
                    email=user.email,
                )
                user = await self.repository.set_clerk_user_id(user_id, clerk_resp["id"])
            except ClerkApiError as exc:
                status = 502 if exc.status_code >= 500 else 400
                raise HTTPException(status_code=status, detail=exc.message) from exc
        else:
            try:
                await self.clerk.update_user(user.clerk_user_id, password=password)
            except ClerkApiError as exc:
                status = 502 if exc.status_code >= 500 else 400
                raise HTTPException(status_code=status, detail=exc.message) from exc

        return await self.update_password(user_id, password)

    async def toggle_user(self, user_id: UUID):
        existing = await self.repository.get_user_by_id(user_id)
        self._ensure_same_brand(existing)
        clerk_id = existing.clerk_user_id
        result = await self.repository.toggle_user(user_id)

        if clerk_id:
            updated = await self.repository.get_user_by_id(user_id)
            try:
                if updated.active:
                    await self.clerk.unban_user(clerk_id)
                else:
                    await self.clerk.ban_user(clerk_id)
            except ClerkApiError as exc:
                status = 502 if exc.status_code >= 500 else 400
                raise HTTPException(status_code=status, detail=exc.message) from exc

        return result
