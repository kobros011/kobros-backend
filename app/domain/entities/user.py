from dataclasses import dataclass
from app.domain.entities.base import Base
from app.infrastructure.models.user_model import UserType
from uuid import UUID
from typing import Optional

@dataclass
class User(Base):
    username: str = ""
    hashed_password: str = ""
    name: Optional[str] = ""
    last_name: Optional[str] = ""
    type_user: UserType = ""
    brand_id: Optional[UUID] = None
