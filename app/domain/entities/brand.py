from dataclasses import dataclass
from app.domain.entities.base import Base

@dataclass
class Brand(Base):
    name: str = ""
    code: str = ""
    routes_available: int = 0