from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from app.domain.entities.base import Base


@dataclass
class ClientContact(Base):
    kind: str = "referencia"
    name: str = ""
    phone: str = ""
    address: Optional[str] = None
    position: int = 1
    client_id: UUID = None
