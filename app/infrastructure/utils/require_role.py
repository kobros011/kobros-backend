from fastapi import Depends, HTTPException
from app.infrastructure.utils.require_authentication import get_current_user
from app.infrastructure.models.user_model import UserModel


def require_role(*allowed_roles: str):
    async def dependency(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        role_value = current_user.type_user.value if hasattr(current_user.type_user, "value") else str(current_user.type_user)
        if role_value not in allowed_roles:
            raise HTTPException(status_code=403, detail="Sin permisos suficientes")
        return current_user
    return dependency
