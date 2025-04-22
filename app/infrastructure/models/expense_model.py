from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID


class ExpenseModel(Base):
    __tablename__ = "expenses"

    date = Column(DateTime, nullable=False)
    value = Column(Float(2, True), nullable=False)
    name = Column(String)
    type = Column(String)
    concept = Column(Text)

    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"))
    route = relationship("RouteModel", back_populates="expenses")
