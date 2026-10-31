from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class ClientRouteRead(BaseModel):
    id: UUID
    order: int
    full_name: str
    id_document: str
    client_id: UUID
    route_id: UUID
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class ClientRouteCreate(BaseModel):
    order: int
    client_id: UUID
    route_id: UUID

class ClientRouteUpdate(BaseModel):
    id: UUID
    order: int
