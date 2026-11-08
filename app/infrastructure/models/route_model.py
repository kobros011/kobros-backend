from sqlalchemy import Column, ForeignKey, Float, Date, String, Integer
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID, ARRAY


class RouteModel(Base):
    __tablename__ = "routes"

    name = Column(String, nullable=False)
    initial_value = Column(Float(2, True), nullable=False)
    initial_expense = Column(Float(2, True), nullable=False)
    opening_date = Column(Date, nullable=False)
    loans_number = Column(Integer, default=0, nullable=False)
    currency = Column(String(3), nullable=False)  # una de las monedas de la marca
    allowed_users_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)

    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)
    brand = relationship("BrandModel", back_populates="routes")

    expenses = relationship("ExpenseModel", back_populates="route")
    liquidations = relationship("LiquidationModel", back_populates="route")
    clientsroutes = relationship("ClientRouteModel", back_populates="route")