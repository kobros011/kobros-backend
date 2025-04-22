from dataclasses import dataclass
from .base import Base
from uuid import UUID

@dataclass
class ClientRoute(Base):
    order: int = 0
    client_id: UUID = None
    route_id: UUID = None