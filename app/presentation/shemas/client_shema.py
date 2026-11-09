from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class ClientReferenceRead(BaseModel):
    id: UUID
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None


class ClientReferenceCreate(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None


class ClientRouteInfoRead(BaseModel):
    """Prioridad del cliente en una de sus rutas (1 = primero en visitarse)."""
    route_id: UUID
    route_name: str = ""
    clientroute_id: UUID
    order: int
    route_total: int = 0  # clientes activos de la ruta ("#2 de 38")


class ClientRead(BaseModel):
    id: UUID
    full_name: str
    id_document: str
    current_address: Optional[str]
    current_phone: Optional[str]
    current_mobile: Optional[str]
    neighborhood: Optional[str]
    linking_date: Optional[datetime]
    beak: Optional[float]
    routes_ids: list[UUID] = []
    routes: List[ClientRouteInfoRead] = []
    brand_id: UUID
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    guarantor_name: Optional[str] = None
    guarantor_cedula: Optional[str] = None
    guarantor_phone: Optional[str] = None
    guarantor_address: Optional[str] = None
    references: List[ClientReferenceRead] = []
    active_loans_count: int = 0


class ClientMoreInfoRead(ClientRead):
    route_name: Optional[str] = ""
    route_id: Optional[UUID] = None
    order: Optional[int] = None


class ClientRouteInput(BaseModel):
    """Ruta a la que se asigna el cliente al crearlo, con su prioridad (vacía = al final de la ruta)."""
    route_id: UUID
    order: Optional[int] = Field(default=None, ge=1)


class ClientCreate(BaseModel):
    full_name: str
    id_document: str
    current_address: str
    current_phone: str
    current_mobile: str
    neighborhood: str
    linking_date: datetime
    routes_ids: list[UUID] = []
    routes: List[ClientRouteInput] = []
    brand_id: UUID

    guarantor_name: Optional[str] = None
    guarantor_cedula: Optional[str] = None
    guarantor_phone: Optional[str] = None
    guarantor_address: Optional[str] = None
    references: List[ClientReferenceCreate] = []

    @field_validator("references")
    @classmethod
    def max_two_references(cls, v):
        if len(v) > 2:
            raise ValueError("El cliente puede tener mÃ¡ximo 2 referencias")
        return v

    def route_positions(self) -> dict[UUID, Optional[int]]:
        """Ruta -> prioridad pedida (None = al final). `routes` manda sobre `routes_ids`; sin repetidos."""
        wanted: dict[UUID, Optional[int]] = {}
        for item in self.routes:
            wanted.setdefault(item.route_id, item.order)
        for route_id in self.routes_ids:
            wanted.setdefault(route_id, None)
        return wanted


class ClientUpdate(BaseModel):
    id: UUID = None
    full_name: str = ""
    id_document: str = ""
    current_address: str = ""
    current_phone: str = ""
    current_mobile: str = ""
    neighborhood: str = ""
    routes_ids: Optional[List[UUID]] = None  # None = no tocar las rutas del cliente

    guarantor_name: Optional[str] = None
    guarantor_cedula: Optional[str] = None
    guarantor_phone: Optional[str] = None
    guarantor_address: Optional[str] = None
    references: Optional[List[ClientReferenceCreate]] = None

    @field_validator("references")
    @classmethod
    def max_two_references(cls, v):
        if v is not None and len(v) > 2:
            raise ValueError("El cliente puede tener mÃ¡ximo 2 referencias")
        return v


class ClientFilters(BaseModel):
    active: bool
    text: str
    route_id: UUID

