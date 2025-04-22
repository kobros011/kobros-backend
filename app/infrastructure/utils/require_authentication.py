from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.auth import SECRET_KEY, ALGORITHM, get_user
from app.infrastructure.models.user_model import UserModel
from jwt import decode, DecodeError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


async def require_authentication(token: str = Depends(oauth2_scheme)) -> UserModel:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Las credenciales no son validas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
    except DecodeError:
        raise credentials_exception
    user = get_user(username)

    if not user:
        raise credentials_exception
    return user
