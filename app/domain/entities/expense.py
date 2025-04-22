from dataclasses import dataclass
from .base import Base
from typing import Optional
from datetime import datetime
from uuid import UUID


@dataclass
class Expense(Base):
    date: Optional[datetime] = None
    value: float = ""
    name: str = ""
    type: str = ""
    concept: str = ""

    route_id: UUID = None
