from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class ClientRouteRead(BaseModel):
    id: UUID
    order: int
    client_id: UUID
    route_id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime

class ClientRouteCreate(BaseModel):
    order: int
    client_id: UUID
    route_id: UUID

class ClientRouteUpdate(BaseModel):
    id: UUID
    order: int