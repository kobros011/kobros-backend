from dataclasses import dataclass
from .base import Base
from uuid import UUID

@dataclass
class ClientRoute(Base):
    order: int = 0
    full_name: str = ""
    id_document: str = ""
    client_id: UUID = None
    route_id: UUID = None
    route_name: str = ""
    neighborhood: str = ""
    current_mobile: str = ""
    client_active: bool = True

@dataclass(frozen=True)
class RouteInfo:
    route_name: str = ""
    route_id: UUID = None
    order: int = 0