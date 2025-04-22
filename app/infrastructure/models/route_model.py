from sqlalchemy import Column, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID


class RouteModel(Base):
    __tablename__ = "routes"

    initial_value = Column(Float(2, True), nullable=False)
    initial_expense = Column(Float(2, True), nullable=False)
    opening_date = Column(DateTime)

    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"))
    brand = relationship("BrandModel", back_populates="routes")

    expenses = relationship("ExpenseModel", back_populates="route")
    liquidations = relationship("LiquidationModel", back_populates="route")
    clientsroutes = relationship("ClientRouteModel", back_populates="route")