from dataclasses import dataclass
from .base import Base
from typing import Optional
from datetime import datetime
from uuid import UUID

@dataclass
class ExpenseConcept(Base):
    concept: str = ""
    keyIcon: str = ""
    color: str = ""

    brand_id: UUID = None

@dataclass
class Expense(Base):
    date: Optional[datetime] = None
    value: float = ""
    name: str = ""

    expensesconcept_id: UUID = None
    user_generated: str = ""
    created_by: Optional[UUID] = None
    expenseconcept: Optional[ExpenseConcept] = None

    liquidated: bool = False
    date_liquidated: Optional[datetime] = None

    route_id: UUID = None
