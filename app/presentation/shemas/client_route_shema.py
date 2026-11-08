from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import Field

class ClientRouteRead(BaseModel):
    id: UUID
    order: int
    full_name: str
    id_document: str
    client_id: UUID
    route_id: UUID
    route_name: str = ""
    neighborhood: str = ""
    current_mobile: str = ""
    client_active: bool = True
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


class ClientRouteMove(BaseModel):
    """Mueve un cliente a `position` dentro de su ruta (1 = primero)."""
    position: int = Field(ge=1)


class ClientRouteReorder(BaseModel):
    """Orden completo de una ruta: todos sus `clientroute_id` activos, del primero al último."""
    route_id: UUID
    ordered_ids: List[UUID] = Field(min_length=1)


class ClientRouteBulkMove(BaseModel):
    route_id: UUID
    clientroute_ids: List[UUID] = Field(min_length=1)
    target: Literal["start", "end", "position"]
    position: Optional[int] = Field(default=None, ge=1)
