from sqlalchemy import Column, String, Text, Enum, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.models.models import UserType

class UserModel(Base):
    __tablename__ = "users"

    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    hashed_password = Column(Text, nullable=False)
    full_name = Column(String, nullable=True)
    type_user = Column(Enum(UserType), nullable=False)

    ## DATA USER
    document_id = Column(String, nullable=True)
    linking_date = Column(Date, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    city = Column(String, nullable=True)
    department = Column(String, nullable=True)

    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    brand = relationship("BrandModel", back_populates="users")

    clerk_user_id = Column(String(64), unique=True, nullable=True)