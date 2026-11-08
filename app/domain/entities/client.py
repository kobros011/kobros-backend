from dataclasses import dataclass, field
from app.domain.entities.base import Base
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Any

@dataclass
class Client(Base):
    full_name: str = ""
    id_document: str = ""
    current_address: str = ""
    current_phone: str = ""
    neighborhood: str = ""
    current_mobile: str = ""
    linking_date: datetime = ""
    beak: float = ""
    routes_ids: List[UUID] = field(default_factory=list)
    routes: List[Any] = field(default_factory=list)

    brand_id: UUID = None

    guarantor_name: Optional[str] = None
    guarantor_cedula: Optional[str] = None
    guarantor_phone: Optional[str] = None
    guarantor_address: Optional[str] = None
    references: List[Any] = field(default_factory=list)
    active_loans_count: int = 0

@dataclass
class ClientById(Client):
    route_name: str = ""
    route_id: UUID = None
    order: int = 0