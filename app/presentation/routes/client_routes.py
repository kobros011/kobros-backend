from fastapi import APIRouter, Depends, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.client_repository import ClientRepository
from ...use_cases.client_cases import ClientUseCases
from ..shemas.client_shema import ClientRead, ClientUpdate, ClientCreate, ClientMoreInfoRead
from ...use_cases.client_cases import ClientUseCases
from ...infrastructure.utils.require_authentication import require_authentication
from app.infrastructure.models.user_model import UserModel


router = APIRouter(dependencies=[Depends(require_authentication)])

def get_client_repository(db: AsyncSession = Depends(get_db)) -> ClientRepository:
    return ClientRepository(db)

def get_client_usecases(user: UserModel = Depends(require_authentication), repository: ClientRepository = Depends(get_client_repository)) -> ClientUseCases:
    usecases = ClientUseCases(repository=repository)
    usecases.user = user
    repository.user = user 
    return usecases

@router.get("/{client_id}", response_model=Optional[ClientRead])
async def read_client(client_id: UUID, usecases: ClientUseCases = Depends(get_client_usecases)):
    return await usecases.get_client(client_id)
@router.get("/{client_id}/more_info/", response_model=Optional[ClientMoreInfoRead])
async def read_client(client_id: UUID, route_id: Optional[UUID] = Query(None), usecases: ClientUseCases = Depends(get_client_usecases)):
    return await usecases.get_client_more_info(client_id, route_id)

@router.get("/", response_model=List[ClientRead])
async def list_clients(request: Request, usecases: ClientUseCases = Depends(get_client_usecases)):
    filters = dict(request.query_params)
    return await usecases.list_clients(filters)

@router.post("/", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(client_in: ClientCreate, usecases: ClientUseCases = Depends(get_client_usecases)):
    return await usecases.create_client(client=client_in)

@router.put("/{client_id}", response_model=ClientRead)
async def update_client(client_in: ClientUpdate, usecases: ClientUseCases = Depends(get_client_usecases)):
    return await usecases.update_client(client=client_in)

@router.put("/{client_id}/toggle")
async def toggle_client(client_id: UUID, usecases: ClientUseCases = Depends(get_client_usecases)):
    return await usecases.toggle_client(client_id)