from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Optional


class RouteRead(BaseModel):
    id: UUID
    name: str
    initial_value: float
    initial_expense: float
    opening_date: datetime
    brand_id: UUID
    allowed_users_ids: List[UUID]
    loans_number: int
    currency: str
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]


class RouteCreate(BaseModel):
    name: str
    initial_value: float
    initial_expense: float
    opening_date: datetime
    brand_id: UUID
    allowed_users_ids: List[UUID]
    # Obligatoria solo si la marca tiene más de una moneda; con una sola se usa esa.
    currency: Optional[str] = None


class RouteUpdate(BaseModel):
    id: UUID
    name: str
    initial_value: float
    initial_expense: float
    opening_date: datetime
    allowed_users_ids: List[UUID]
    currency: Optional[str] = None  # None = sin cambio


class RouteCurrencyRead(BaseModel):
    id: UUID
    currency: str


class RouteFilters(BaseModel):
    active: bool
    text: str

