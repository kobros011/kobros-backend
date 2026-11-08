from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID
from app.domain.entities.client_route import RouteInfo


class ClientRouteModel(Base):
    __tablename__ = "clientsroutes"

    order = Column(Integer, nullable=False)

    cliente_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"))
    client = relationship("ClientModel", back_populates="clientsroutes")

    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"))
    route = relationship("RouteModel", back_populates="clientsroutes", lazy="selectin")

    loans = relationship("LoanModel", back_populates="clientroute")

    @property
    def info_data(self) -> RouteInfo:
        return RouteInfo(
            order=self.order,
            route_id=self.route_id,
            route_name=self.route.name,
        )