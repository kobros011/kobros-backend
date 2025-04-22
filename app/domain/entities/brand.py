from dataclasses import dataclass
from app.domain.entities.base import Base

@dataclass
class Brand(Base):
    name: str = ""
    code: str = ""
    loans_number: int = 0