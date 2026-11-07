from dataclasses import dataclass
from app.domain.entities.base import Base
from uuid import UUID
from typing import Optional


@dataclass
class RouteMovement(Base):
    route_id: UUID = ""
    type: str = ""
    value: float = 0
    concept: str = ""
    user_id: Optional[UUID] = None
    user_name: str = ""
