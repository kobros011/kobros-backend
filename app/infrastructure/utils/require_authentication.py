from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.core.auth import verify_clerk_token
from app.infrastructure.models.user_model import UserModel
from app.infrastructure.dababase.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

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

    result = await db.execute(
        select(UserModel).where(UserModel.clerk_user_id == clerk_user_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no registrado en Kobros")
    if not user.active:
        raise HTTPException(status_code=403, detail="Usuario inactivo")
    return user


require_authentication = get_current_user
