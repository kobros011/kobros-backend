from dataclasses import dataclass
from app.domain.entities.base import Base
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from pydantic import Field

@dataclass
class Route(Base):
    name: str = ""
    initial_value: float = ""
    initial_expense: float = ""
    opening_date: Optional[datetime] = None
    loans_number: int = 0
    allowed_users_ids: List[UUID] = Field(default_factory=List)

    brand_id: UUID = ""