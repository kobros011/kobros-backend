from sqlalchemy import Column, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID


class RouteMovementModel(Base):
    __tablename__ = "route_movements"

    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    route = relationship("RouteModel")

    type = Column(String, nullable=False)  # 'INGRESO' | 'RETIRO'
    value = Column(Float(2, True), nullable=False)
    concept = Column(String, nullable=False)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user = relationship("UserModel")
