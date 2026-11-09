from fastapi import APIRouter, Depends, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List, Union
from ...core.exceptions import BadRequestException
from ...core.pagination import Page, PaginationParams, filters_from_request, optional_pagination_params
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.client_repository import ClientRepository
from ...use_cases.client_cases import ClientUseCases
from ..shemas.client_shema import ClientRead, ClientUpdate, ClientCreate, ClientMoreInfoRead
from ...use_cases.client_cases import ClientUseCases
from ...infrastructure.utils.require_authentication import require_authentication, get_current_user
from ...infrastructure.utils.require_role import require_role
from ...infrastructure.utils.access import ensure_client_access, ensure_route_access
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
async def read_client(
    client_id: UUID,
    usecases: ClientUseCases = Depends(get_client_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    await ensure_client_access(db, client_id, user)
    return await usecases.get_client(client_id)
@router.get("/{client_id}/more_info/", response_model=Optional[ClientMoreInfoRead])
async def read_client_more_info(
    client_id: UUID,
    route_id: Optional[UUID] = Query(None),
    usecases: ClientUseCases = Depends(get_client_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    await ensure_client_access(db, client_id, user)
    if route_id:
        await ensure_route_access(db, route_id, user)
    return await usecases.get_client_more_info(client_id, route_id)

@router.get("/", response_model=Union[Page[ClientRead], List[ClientRead]])
async def list_clients(
    request: Request,
    pagination: Optional[PaginationParams] = Depends(optional_pagination_params),
    usecases: ClientUseCases = Depends(get_client_usecases),
):
    return await usecases.list_clients(filters_from_request(request), pagination)

@router.post("/", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(
    client_in: ClientCreate,
    usecases: ClientUseCases = Depends(get_client_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    route_ids = list(client_in.route_positions())
    if not route_ids:
        raise BadRequestException("Elige al menos una ruta para el cliente")
    for route_id in route_ids:  # la ruta debe ser de la marca del usuario y, para socio y cobrador, una asignada
        await ensure_route_access(db, route_id, user)
    return await usecases.create_client(client=client_in)

@router.put("/{client_id}", response_model=ClientRead)
async def update_client(
    client_in: ClientUpdate,
    usecases: ClientUseCases = Depends(get_client_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    await ensure_client_access(db, client_in.id, user)
    return await usecases.update_client(client=client_in)

@router.put("/{client_id}/toggle")
async def toggle_client(
    client_id: UUID,
    usecases: ClientUseCases = Depends(get_client_usecases),
    user: UserModel = Depends(require_role("01", "02", "03")),
    db: AsyncSession = Depends(get_db),
):
    await ensure_client_access(db, client_id, user)
    return await usecases.toggle_client(client_id)