from dataclasses import dataclass
from app.domain.entities.base import Base
from uuid import UUID
from typing import Optional
from datetime import datetime

@dataclass
class Route(Base):
    initial_value: float = ""
    initial_expense: float = ""
    opening_date: Optional[datetime] = None

    brand_id = UUID