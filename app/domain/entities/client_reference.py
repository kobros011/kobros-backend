from dataclasses import dataclass
from app.domain.entities.base import Base
from uuid import UUID


@dataclass
class ClientReference(Base):
    name: str = ""
    address: str = ""
    phone: str = ""
    client_id: UUID = None
