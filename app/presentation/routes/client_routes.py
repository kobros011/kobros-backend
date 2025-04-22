from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.client_repository import ClientRepository
from ...use_cases.client_cases import ClientUseCases
from ..shemas.client_shema import ClientRead, ClientUpdate, ClientCreate
from ...use_cases.client_cases import ClientUseCases
from ...infrastructure.utils.require_authentication import require_authentication

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_client_repository(db: AsyncSession = Depends(get_db)) -> ClientRepository:
    return ClientRepository(db)

def get_client_usecases(repository: ClientRepository = Depends(get_client_repository)) -> ClientUseCases:
    return ClientUseCases(repository)

@router.get("/{client_id}", response_model=Optional[ClientRead])
async def read_client(client_id: UUID, usecases: ClientUseCases = Depends(get_client_usecases)):
    return await usecases.get_client(client_id)

@router.get("/", response_model=List[ClientRead])
async def list_clients(usecases: ClientUseCases = Depends(get_client_usecases)):
    return await usecases.list_clients()

@router.post("/", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(client_in: ClientCreate, usecases: ClientUseCases = Depends(get_client_usecases)):
    return await usecases.create_client(client=client_in)

@router.put("/{client_id}", response_model=ClientRead)
async def update_client(client_in: ClientUpdate, usecases: ClientUseCases = Depends(get_client_usecases)):
    return await usecases.update_client(client=client_in)

@router.delete("/{client_id}")
async def delete_client(client_id: UUID, usecases: ClientUseCases = Depends(get_client_usecases)):
    return await usecases.delete_client(client_id)