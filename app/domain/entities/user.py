from dataclasses import dataclass, field
from app.domain.entities.base import Base
from app.infrastructure.models.user_model import UserType
from uuid import UUID
from typing import Optional
from datetime import datetime

@dataclass
class User(Base):
    username: str = ""
    email: Optional[str] = None
    hashed_password: str = ""
    full_name: str = ""
    document_id: str = ""
    linking_date: datetime = field(default_factory=datetime.now)
    address: Optional[str] = ""
    phone: Optional[str] = ""
    mobile: Optional[str] = ""
    city: Optional[str] = ""
    department: Optional[str] = ""
    type_user: UserType = ""
    brand_id: Optional[UUID] = None
    clerk_user_id: Optional[str] = None
