from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from ...infrastructure.dababase.db import get_db
from ...infrastructure.repositories.route_repository import RouteRepository
from ...use_cases.route_cases import RouteUseCases
from ..shemas.route_shema import RouteRead, RouteUpdate, RouteCreate
from ...use_cases.route_cases import RouteUseCases
from ...infrastructure.utils.require_authentication import require_authentication

router = APIRouter(dependencies=[Depends(require_authentication)])

def get_route_repository(db: AsyncSession = Depends(get_db)) -> RouteRepository:
    return RouteRepository(db)

def get_route_usecases(repository: RouteRepository = Depends(get_route_repository)) -> RouteUseCases:
    return RouteUseCases(repository)

@router.get("/{route_id}", response_model=Optional[RouteRead])
async def read_route(route_id: UUID, usecases: RouteUseCases = Depends(get_route_usecases)):
    return await usecases.get_route(route_id)

@router.get("/", response_model=List[RouteRead])
async def list_routes(usecases: RouteUseCases = Depends(get_route_usecases)):
    return await usecases.list_routes()

@router.post("/", response_model=RouteRead, status_code=status.HTTP_201_CREATED)
async def create_route(route_in: RouteCreate, usecases: RouteUseCases = Depends(get_route_usecases)):
    return await usecases.create_route(route=route_in)

@router.put("/{route_id}", response_model=RouteRead)
async def update_route(route_in: RouteUpdate, usecases: RouteUseCases = Depends(get_route_usecases)):
    return await usecases.update_route(route=route_in)

@router.delete("/{route_id}")
async def delete_route(route_id: UUID, usecases: RouteUseCases = Depends(get_route_usecases)):
    return await usecases.delete_route(route_id)