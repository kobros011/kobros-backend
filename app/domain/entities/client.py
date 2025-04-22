from dataclasses import dataclass
from app.domain.entities.base import Base
from uuid import UUID

@dataclass
class Client(Base):
    full_name: str = ""
    id_document: str = ""
    current_address: str = ""
    current_phone: str = ""

    brand_id = UUID = None