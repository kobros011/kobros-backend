from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class ExpenseRead(BaseModel):
    id: UUID
    date: datetime
    value: float
    name: str
    type: str
    concept:str
    route_id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime

class ExpenseCreate(BaseModel):
    date: datetime
    value: float
    name: str
    type: str
    concept:str
    route_id: UUID

class ExpenseUpdate(BaseModel):
    id: UUID
    date: datetime
    value: float
    name: str
    type: str
    concept:str
