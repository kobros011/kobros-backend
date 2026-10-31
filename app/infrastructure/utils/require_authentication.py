from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.core.auth import verify_clerk_token
from app.infrastructure.models.user_model import UserModel
from app.infrastructure.dababase.db import get_db
from app.infrastructure.utils.clerk_user_resolve import resolve_user_by_clerk_subject
from sqlalchemy.ext.asyncio import AsyncSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    if not token:
        raise HTTPException(status_code=401, detail="No se proporcionaron credenciales")
    try:
        payload = await verify_clerk_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    clerk_user_id: str = payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Token sin subject")

    user = await resolve_user_by_clerk_subject(db, clerk_user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail=(
                "Usuario no registrado en Kobros. "
                "Pide a un administrador que te dé de alta o ejecute sync_users_to_clerk."
            ),
        )
    if not user.active:
        raise HTTPException(status_code=403, detail="Usuario inactivo")
    return user


require_authentication = get_current_user
