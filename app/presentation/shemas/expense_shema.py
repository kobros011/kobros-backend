from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class ExpenseConceptRead(BaseModel):
    id: UUID
    concept: str
    keyIcon: str
    color: str
    brand_id: UUID

class ExpenseConceptCreate(BaseModel):
    concept: str
    keyIcon: str
    color: str
    brand_id: UUID

class ExpenseConceptUpdate(BaseModel):
    id: UUID
    concept: str
    keyIcon: str
    color: str

class ExpenseRead(BaseModel):
    id: UUID
    date: datetime
    value: float
    name: str
    route_id: UUID
    expensesconcept_id: UUID
    expenseconcept: Optional[ExpenseConceptRead] = None
    user_generated: str
    liquidated: bool = False
    date_liquidated: Optional[datetime] = None
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class ExpenseCreate(BaseModel):
    date: datetime
    value: float
    name: str
    expensesconcept_id: UUID
    route_id: UUID
    user_generated: str

class ExpenseUpdate(BaseModel):
    id: UUID
    date: datetime
    value: float
    name: str
    expensesconcept_id: UUID
    route_id: UUID

class ExpenseFilters(BaseModel):
    text: str
    route_id: UUID
    date: str
    expense_concept_id: UUID
    date_liquidated: str
    expenses_today: bool
