from sqlalchemy import Column, String, Text, ForeignKey, Date, Float
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID
from typing import Optional, List
from app.domain.entities.client_route import RouteInfo
from app.infrastructure.models.client_route_model import ClientRouteModel

class ClientModel(Base):
    __tablename__ = "clients"

    full_name = Column(String, nullable=False)
    id_document = Column(String, nullable=False)
    current_address = Column(Text)
    neighborhood = Column(String)
    current_phone = Column(String)
    current_mobile = Column(String)
    linking_date = Column(Date, nullable=True)
    beak = Column(Float, default=0, nullable=True) ## Pico o saldo a favor del cliente


    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"))
    brand = relationship("BrandModel", back_populates="clients")

    clientsroutes = relationship("ClientRouteModel", back_populates="client")
    references = relationship("ClientReferenceModel", back_populates="client", cascade="all, delete-orphan")

    guarantor_name = Column(String, nullable=True)
    guarantor_cedula = Column(String, nullable=True)
    guarantor_phone = Column(String, nullable=True)
    guarantor_address = Column(String, nullable=True)


    def get_route_info(self, *, route_id: Optional[UUID] = None) -> Optional[RouteInfo]:

        clientsroutes: List[ClientRouteModel] = self.clientsroutes

        infos = []
        for cr in clientsroutes:
            infos.append(cr.info_data)

        for info in infos:
            if info.route_id == route_id:
                return info
            
        return RouteInfo()