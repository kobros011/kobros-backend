from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.infrastructure.dababase.db import get_db
from app.infrastructure.repositories.user_repository import UserRepository
from app.presentation.shemas.user_shema import UserCreate, UserRead, UserUpdate
from app.use_cases.user_cases import UserUseCases
from app.infrastructure.utils.require_authentication import require_authentication

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)

def get_user_usecases(repository: UserRepository = Depends(get_user_repository)) -> UserUseCases:
    return UserUseCases(repository)

@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(user_in:UserCreate, usecases: UserUseCases = Depends(get_user_usecases)):
    user = await usecases.create_user(user=user_in)
    return user

@router.get("/", response_model=list[UserRead])
async def list_users(usecases: UserUseCases = Depends(get_user_usecases)):
    return await usecases.list_users()

@router.get("/{user_id}", response_model=UserRead)
async def read_user(user_id: UUID, usecases: UserUseCases = Depends(get_user_usecases)):
    user = await usecases.get_user(user_id)
    return user

@router.put("/{user_id}", response_model=UserRead)
async def update_user(user_in: UserUpdate, usecases: UserUseCases = Depends(get_user_usecases)):
    user = await usecases.update_user(user=user_in)
    return user

@router.delete("/{user_id}")
async def delete_user(user_id: UUID, usecases: UserUseCases = Depends(get_user_usecases)):
    return await usecases.delete_user(user_id)