from sqlalchemy import Column, String, ForeignKey, Integer, Float, Date, Boolean
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID

class PaymentModel(Base):
    __tablename__ = "payments"

    pay_date = Column(Date)
    payment_date = Column(Date, nullable=True)
    quota_number = Column(Integer, nullable=False)
    value = Column(Float(2, True))
    credit_value = Column(Float(2, True))
    status = Column(String)
    applied = Column(Float(2, True))

    liquidated: bool = Column(Boolean, default=False)
    date_liquidated = Column(Date, nullable=True)

    loan_id = Column(UUID(as_uuid=True), ForeignKey("loans.id"))
    loan = relationship("LoanModel", back_populates="payments")