from dataclasses import dataclass
from .base import Base
from typing import Optional
from datetime import datetime
from uuid import UUID

@dataclass
class Liquidation(Base):
    date: Optional[datetime] = None
    today_collection_goal: float = ""
    value_base_delivered: float = ""
    total_value_charged: float = ""
    total_value_expenses: float = ""
    value_new_loans: float = ""

    route_id: UUID = None