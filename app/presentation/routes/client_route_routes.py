from fastapi import APIRouter, Depends, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.client_route_repository import ClientRouteRepository
from ...use_cases.client_route_cases import ClientRouteUseCases
from ..shemas.client_route_shema import ClientRouteRead, ClientRouteCreate, ClientRouteUpdate, ClientRouteMove, ClientRouteReorder, ClientRouteBulkMove
from ...use_cases.client_route_cases import ClientRouteUseCases
from ...infrastructure.utils.require_authentication import require_authentication, get_current_user
from ...infrastructure.utils.require_role import require_role
from ...infrastructure.utils.access import ensure_clientroute_access, ensure_route_access
from ...core.exceptions import BadRequestException, NotFoundException
from app.infrastructure.models.user_model import UserModel

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_client_route_repository(db: AsyncSession = Depends(get_db)) -> ClientRouteRepository:
    return ClientRouteRepository(db)

def get_client_route_usecases(user: UserModel = Depends(require_authentication), repository: ClientRouteRepository = Depends(get_client_route_repository)) -> ClientRouteUseCases:
    usecases = ClientRouteUseCases(repository=repository)
    usecases.user = user
    repository.user = user 
    return usecases

@router.post("/", response_model=ClientRouteRead, status_code=status.HTTP_201_CREATED)
async def create_client_route(
    client_route_in: ClientRouteCreate,
    usecases: ClientRouteUseCases = Depends(get_client_route_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    await ensure_route_access(db, client_route_in.route_id, user)
    return await usecases.create_client_route(client_route=client_route_in)

@router.get("/{client_route_id}", response_model=Optional[ClientRouteRead])
async def read_client_route(
    client_route_id: UUID,
    usecases: ClientRouteUseCases = Depends(get_client_route_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    await ensure_clientroute_access(db, client_route_id, user)
    return await usecases.get_client_route(client_route_id)

@router.get("/", response_model=List[ClientRouteRead])
async def list_client_routes(
    route_id: Optional[UUID] = Query(None),
    usecases: ClientRouteUseCases = Depends(get_client_route_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if route_id is None:  # sin ruta devolvería los clientes de todas las marcas
        raise BadRequestException("route_id es requerido")
    await ensure_route_access(db, route_id, user)
    return await usecases.list_client_routes(route_id)

@router.put("/reorder", response_model=List[ClientRouteRead])
async def reorder_route_clients(
    body: ClientRouteReorder,
    usecases: ClientRouteUseCases = Depends(get_client_route_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_role("01", "02", "03")),
):
    await ensure_route_access(db, body.route_id, user)
    return await usecases.reorder_route(body.route_id, body.ordered_ids)

@router.post("/bulk-move", response_model=List[ClientRouteRead])
async def bulk_move_route_clients(
    body: ClientRouteBulkMove,
    usecases: ClientRouteUseCases = Depends(get_client_route_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_role("01", "02", "03")),
):
    if body.target == "position" and body.position is None:
        raise BadRequestException("Indica la posición de destino")
    await ensure_route_access(db, body.route_id, user)
    return await usecases.bulk_move(body.route_id, body.clientroute_ids, body.target, body.position)

@router.put("/{client_route_id}/order", response_model=List[ClientRouteRead])
async def move_route_client(
    client_route_id: UUID,
    body: ClientRouteMove,
    usecases: ClientRouteUseCases = Depends(get_client_route_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_role("01", "02", "03")),
):
    await ensure_clientroute_access(db, client_route_id, user)
    return await usecases.move_client_route(client_route_id, body.position)

@router.put("/{client_route_id}", response_model=ClientRouteRead)
async def update_client_route(
    client_route_in: ClientRouteUpdate,
    usecases: ClientRouteUseCases = Depends(get_client_route_usecases),
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(require_role("01", "02", "03")),
):
    await ensure_clientroute_access(db, client_route_in.id, user)
    await usecases.move_client_route(client_route_in.id, client_route_in.order)  # recorre a los demás: sin duplicados
    return await usecases.get_client_route(client_route_in.id)