from sqlalchemy import Column, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID

class LiquidationModel(Base):
    __tablename__ = "liquidations"

    date = Column(DateTime)
    today_collection_goal = Column(Float(2, True))
    value_base_delivered = Column(Float(2, True))
    total_value_charged = Column(Float(2, True))
    total_value_expenses = Column(Float(2, True))
    value_new_loans = Column(Float(2, True))
    
    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"))
    route = relationship("RouteModel", back_populates="liquidations")