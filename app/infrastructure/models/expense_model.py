from sqlalchemy import Column, String, Boolean, ForeignKey, Date, Float
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID


class ExpenseModel(Base):
    __tablename__ = "expenses"

    date = Column(Date, nullable=False)
    value = Column(Float(2, True), nullable=False)
    name = Column(String, nullable=False)

    expensesconcept_id = Column(UUID(as_uuid=True), ForeignKey("expensesconcept.id"))
    expensesconcept = relationship("ExpenseConceptModel", back_populates="expenses")

    user_generated = Column(String, nullable=False)

    liquidated = Column(Boolean, nullable=False, default=False, server_default="false")
    date_liquidated = Column(Date, nullable=True)
    liquidation_id = Column(UUID(as_uuid=True), ForeignKey("liquidations.id"), nullable=True)
    liquidated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"))
    route = relationship("RouteModel", back_populates="expenses")

class ExpenseConceptModel(Base):
    __tablename__ = "expensesconcept"

    concept = Column(String)
    keyIcon = Column(String)
    color = Column(String)

    expenses = relationship("ExpenseModel", back_populates="expensesconcept")

    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)
    brand = relationship("BrandModel", back_populates="expensesconcept")