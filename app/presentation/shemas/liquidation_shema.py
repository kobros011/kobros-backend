from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class LiquidationRead(BaseModel):
    id: UUID
    date: datetime
    today_collection_goal: float
    value_base_delivered: float
    total_value_charged: float
    total_value_expenses: float
    value_new_loans: float
    route_id: UUID
    collector_id: Optional[UUID] = None
    admin_confirmed_at: Optional[datetime] = None
    admin_confirmed_by: Optional[UUID] = None
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class LiquidationCreate(BaseModel):
    date: datetime
    today_collection_goal: float
    value_base_delivered: float
    value_new_loans: float
    route_id: UUID
    collector_id: Optional[UUID] = None

class LiquidationUpdate(BaseModel):
    id: UUID
    date: Optional[datetime] = None
    today_collection_goal: Optional[float] = None
    value_base_delivered: Optional[float] = None
    value_new_loans: Optional[float] = None
    route_id: Optional[UUID] = None

