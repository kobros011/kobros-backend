from sqlalchemy import Column, ForeignKey, Date, Float, DateTime, Integer, Text
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID

class LiquidationModel(Base):
    __tablename__ = "liquidations"

    date = Column(Date)
    today_collection_goal = Column(Float(2, True))
    value_base_delivered = Column(Float(2, True))
    total_value_charged = Column(Float(2, True))
    total_value_expenses = Column(Float(2, True))
    value_new_loans = Column(Float(2, True))

    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"))
    route = relationship("RouteModel", back_populates="liquidations")

    collector_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    admin_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    admin_confirmed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Cuadre (lo calcula el servidor; `cash_delivered` es el efectivo contado que digita quien cierra)
    cash_delivered = Column(Float, nullable=True)
    expected_cash = Column(Float, nullable=True)
    difference = Column(Float, nullable=True)
    receipts_count = Column(Integer, nullable=False, default=0)
    new_loans_count = Column(Integer, nullable=False, default=0)
    beak_generated = Column(Float, nullable=False, default=0)
    note = Column(Text, nullable=True)
    reopened_at = Column(DateTime(timezone=True), nullable=True)
    reopened_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)