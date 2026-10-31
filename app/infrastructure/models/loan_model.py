from sqlalchemy import Column, String, ForeignKey, Date, Float, Integer, SmallInteger
from sqlalchemy.orm import relationship
from app.infrastructure.dababase.base_class import Base
from sqlalchemy.dialects.postgresql import UUID

class LoanModel(Base):
    __tablename__ = "loans"

    loan_number = Column(Integer, nullable=False) ## Número de préstamo
    initial_date = Column(Date, nullable=False) ## Fecha inicial
    end_date = Column(Date, nullable=False) ## Fecha final
    value_quota_fixed = Column(Float(2, True)) ## Valor de la cuota fija
    pending_quotas = Column(Integer, default=0) ## Cuotas de pendientes
    canceled_quotas = Column(Integer, default=0) ## Cuotas canceladas
    agreed_quotas = Column(Integer, nullable=False) ## Cuotas acordadas
    total_default = Column(Float(2, True), default=0) ## Total de mora
    date_first_quota = Column(Date, nullable=False) ## Fecha de la primera cuota
    payment_method = Column(String, nullable=False) ## Método de pago
    fixed_payment_day = Column(SmallInteger, nullable=True)

    value_capital = Column(Float(2, True)) ## Valor del capital
    value_utility_loan = Column(Float(2, True)) ## Valor de la utilidad del préstamo
    value_total_loan = Column(Float(2, True)) ## Valor del préstamo total
    interest_rate = Column(Float(4, True)) ## Tasa de interés

    clientroute_id = Column(UUID(as_uuid=True), ForeignKey("clientsroutes.id"))
    clientroute = relationship("ClientRouteModel", back_populates="loans")

    payments = relationship("PaymentModel", back_populates="loan")
