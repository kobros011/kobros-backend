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


class RouteUpdate(BaseModel):
    id: UUID
    name: str
    initial_value: float
    initial_expense: float
    opening_date: datetime
    allowed_users_ids: List[UUID]


class RouteFilters(BaseModel):
    active: bool
    text: str

