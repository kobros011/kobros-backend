from pydantic import BaseModel, Field, field_validator, model_validator
from .loan_shema import LoanTerms
from uuid import UUID
from datetime import datetime
from typing import Literal, Optional, List


MAX_CONTACTS = 20


class ClientContactRead(BaseModel):
    id: UUID
    kind: Literal["fiador", "referencia"]
    name: str
    phone: str
    address: Optional[str] = None
    position: int = 1
    is_primary: bool = False


class ClientContactInput(BaseModel):
    """Fiador o referencia del cliente: nombre y celular obligatorios, dirección opcional."""
    kind: Literal["fiador", "referencia"]
    name: str
    phone: str
    address: Optional[str] = None

    @field_validator("name", "phone")
    @classmethod
    def not_blank(cls, v: str):
        v = v.strip()
        if not v:
            raise ValueError("Este dato es obligatorio")
        return v

    @field_validator("address")
    @classmethod
    def clean_address(cls, v: Optional[str]):
        return (v or "").strip() or None


def _limit_contacts(v):
    if v is not None and len(v) > MAX_CONTACTS:
        raise ValueError(f"Un cliente puede tener como máximo {MAX_CONTACTS} fiadores y referencias")
    return v


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

    contacts: List[ClientContactRead] = []
    active_loans_count: int = 0
    # Solo al crear el cliente junto con su primer crédito.
    loan_id: Optional[UUID] = None
    loan_number: Optional[int] = None


class ClientMoreInfoRead(ClientRead):
    route_name: Optional[str] = ""
    route_id: Optional[UUID] = None
    order: Optional[int] = None


class ClientLoanInput(LoanTerms):
    """Primer crédito del cliente nuevo: va en UNA de las rutas del cliente."""
    route_id: UUID


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
    neighborhood: str = ""
    linking_date: datetime
    routes_ids: list[UUID] = []
    routes: List[ClientRouteInput] = []
    loan: Optional[ClientLoanInput] = None
    brand_id: UUID

    contacts: List[ClientContactInput] = []

    _check_contacts = field_validator("contacts")(_limit_contacts)

    @model_validator(mode="after")
    def loan_route_in_routes(self):
        if self.loan is not None and self.loan.route_id not in self.route_positions():
            raise ValueError("La ruta del crédito debe ser una de las rutas del cliente")
        return self

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

    contacts: Optional[List[ClientContactInput]] = None  # None = no tocar; la lista reemplaza a la anterior

    _check_contacts = field_validator("contacts")(_limit_contacts)


class ClientFilters(BaseModel):
    active: bool
    text: str
    route_id: UUID

