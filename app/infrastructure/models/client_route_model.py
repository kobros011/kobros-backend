from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID


class ClientRouteModel(Base):
    __tablename__ = "clientsroutes"

    order = Column(Integer, nullable=False)

    cliente_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"))
    client = relationship("ClientModel", back_populates="clientsroutes")

    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"))
    route = relationship("RouteModel", back_populates="clientsroutes")

    loans = relationship("LoanModel", back_populates="clientroute")
