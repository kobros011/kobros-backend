from sqlalchemy import Column, String, ForeignKey, DateTime, Float, Integer
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID

class LoanModel(Base):
    __tablename__ = "loans"

    loan_number = Column(Integer, nullable=False)
    initial_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    value_quota_fixed = Column(Float(2, True))
    agreed_quotas = Column(Integer, nullable=False)
    date_first_quota = Column(DateTime, nullable=False)
    payment_method = Column(String, nullable=False)

    value_capital = Column(Float(2, True))
    value_utility_loan = Column(Float(2, True))
    value_total_loan = Column(Float(2, True))
    interest_rate = Column(Float(4, True))

    clientroute_id = Column(UUID(as_uuid=True), ForeignKey("clientsroutes.id"))
    clientroute = relationship("ClientRouteModel", back_populates="loans")

    payments = relationship("PaymentModel", back_populates="loan")
