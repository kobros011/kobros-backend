from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal


class RouteMovementRead(BaseModel):
    id: UUID
    route_id: UUID
    type: Literal['INGRESO', 'RETIRO']
    value: float
    concept: str
    user_id: Optional[UUID]
    user_name: str
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]


class RouteMovementCreate(BaseModel):
    route_id: UUID
    type: Literal['INGRESO', 'RETIRO']
    value: float
    concept: str


class RouteCashSummary(BaseModel):
    initial_value: float
    ingresos: float
    retiros: float
    cobros: float
    gastos: float
    desembolsos: float
    saldo: float
