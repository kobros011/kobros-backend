from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base


class BrandModel(Base):
    __tablename__ = "brands"

    name = Column(String, nullable=False)
    code = Column(String, nullable=False)
    loans_number = Column(Integer, default=0, nullable=False)

    users = relationship("UserModel", back_populates="brand")
    clients = relationship("ClientModel", back_populates="brand")
    routes = relationship("RouteModel", back_populates="brand")
