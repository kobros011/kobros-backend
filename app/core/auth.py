from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from app.infrastructure.dababase.db import get_use_db
from sqlalchemy.future import select
from app.infrastructure.models.user_model import UserModel
import bcrypt

SECRET_KEY = "7744f211aa1a9762aa7a73fa88104ecb05b6a6c4f41e8b4de7721c10ae0adbb8"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
REFRESH_TOKEN_EXPIRE_DAYS = 32

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("El token ha expirado")
    except jwt.InvalidTokenError:
        raise Exception("Token inválido")
    

async def get_user(username: str = None, username_id: str = None):
    db = await get_use_db()
    results = await db.execute(select(UserModel).where(UserModel.id == username_id if not username else UserModel.username == username))
    user = results.scalars().first()
    return user

async def authenticate_user(username: str, password: str):
    user = await get_user(username=username)
    if not user: 
        return False
    if not bcrypt.checkpw(password.encode('utf-8'), user.hashed_password.encode('utf-8')):
        return False
    return user