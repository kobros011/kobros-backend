from sqlalchemy import Column, String, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from app.infrastructure.models.models import UserType
from sqlalchemy.dialects.postgresql import UUID

class UserModel(Base):
    __tablename__ = "users"

    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    type_user = Column(Enum(UserType), nullable=False)

    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)

    brand = relationship("BrandModel", back_populates="users")