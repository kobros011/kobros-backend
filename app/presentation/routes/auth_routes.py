from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.core import auth
from app.domain.entities import auth as auth_schemas

router = APIRouter()

@router.post("/login", response_model=auth_schemas.Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await auth.authenticate_user(form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario o contraseña incorrectos",
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no valido"
        )

    access_token = auth.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth.create_refresh_token(data={"sub": str(user.id)})
    return auth_schemas.Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=auth_schemas.Token)
async def refresh_token(token: str):
    try:
        payload = auth.decode_token(token)
        username_id: str = payload.get("sub")
        if not username_id:
            raise HTTPException(status_code=401, detail="Token inválido")

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    user = await auth.get_user(username_id=username_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario no fue encontrado",
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no valido"
        )

    access_token = auth.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth.create_refresh_token(data={"sub": str(user.id)})

    return auth_schemas.Token(access_token=access_token, refresh_token=refresh_token)
