from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class LiquidationRead(BaseModel):
    id: UUID
    date: datetime
    today_collection_goal: str
    value_base_delivered: str
    total_value_charged: str
    total_value_expensess: str
    value_new_loans: str
    route_id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime

class LiquidationCreate(BaseModel):
    date: datetime
    today_collection_goal: str
    value_base_delivered: str
    total_value_charged: str
    total_value_expensess: str
    value_new_loans: str
    route_id: UUID

class LiquidationUpdate(BaseModel):
    id: UUID
    date: datetime
    today_collection_goal: str
    value_base_delivered: str
    total_value_charged: str
    total_value_expensess: str
    value_new_loans: str
    route_id: UUID
