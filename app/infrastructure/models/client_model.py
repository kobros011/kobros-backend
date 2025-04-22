from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID

class ClientModel(Base):
    __tablename__ = "clients"

    full_name = Column(String, nullable=False)
    id_document = Column(String, nullable=False)
    current_address = Column(Text)
    current_phone = Column(String)

    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"))
    brand = relationship("BrandModel", back_populates="clients")

    clientsroutes = relationship("ClientRouteModel", back_populates="client")