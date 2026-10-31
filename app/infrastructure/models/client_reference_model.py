from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID


class ClientReferenceModel(Base):
    __tablename__ = "client_references"

    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    client = relationship("ClientModel", back_populates="references")
