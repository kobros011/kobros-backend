from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class RouteRead(BaseModel):
    id: UUID
    initial_value: float
    initial_expense: float
    opening_date: datetime
    brand_id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime

class RouteCreate(BaseModel):
    initial_value: float
    initial_expense: float
    opening_date: datetime
    brand_id: UUID

class RouteUpdate(BaseModel):
    id: UUID
    initial_value: float
    initial_expense: float
    opening_date: datetime
