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

    contacts: List[Any] = field(default_factory=list)
    active_loans_count: int = 0
    loan_id: Optional[UUID] = None
    loan_number: Optional[int] = None

@dataclass
class ClientById(Client):
    route_name: str = ""
    route_id: UUID = None
    order: int = 0