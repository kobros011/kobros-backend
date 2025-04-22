from sqlalchemy import Column, String, ForeignKey, Integer, Float, DateTime
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID

class PaymentModel(Base):
    __tablename__ = "payments"

    pay_date = Column(DateTime)
    payment_date = Column(DateTime)
    quota_number = Column(Integer, nullable=False)
    value = Column(Float(2, True))
    credit_value = Column(Float(2, True))
    status = Column(String)

    loan_id = Column(UUID(as_uuid=True), ForeignKey("loans.id"))
    loan = relationship("LoanModel", back_populates="payments")