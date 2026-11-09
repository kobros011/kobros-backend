from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional
from ...infrastructure.utils.Emun import PaymentMethod

class LoanRead(BaseModel):
    id: UUID
    loan_number: int
    initial_date: datetime
    end_date: datetime
    value_quota_fixed:float 
    agreed_quotas: int
    pending_quotas: int
    canceled_quotas: int
    date_first_quota: datetime
    payment_method: str
    fixed_payment_day: Optional[int] = None
    value_capital: float
    value_utility_loan: float
    value_total_loan: float
    interest_rate: float
    total_default: float | None = ""
    clientroute_id: UUID
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]
class LoanReadFull(LoanRead):
    client_id: UUID
    client_fullname: str
    client_id_document: str
    client_current_address: str
    client_current_mobile: str
    route_name: str
    route_id: UUID
    order: int
    paid: Optional[float] = None
    balance: Optional[float] = None

class LoanTerms(BaseModel):
    """Condiciones del crédito (las mismas en el asistente y al crearlo junto al cliente)."""
    value_quota_fixed: float = Field(gt=0)
    agreed_quotas: int = Field(ge=1)
    date_first_quota: datetime
    payment_method: str
    fixed_payment_day: Optional[int] = None
    value_capital: float = Field(gt=0)
    # Cobro de la cuota 1 al crear (excedente → saldo a favor del cliente, faltante → mora parcial).
    value_payment: Optional[float] = Field(None, ge=0)

    @model_validator(mode="after")
    def validate_terms(self):
        if self.payment_method not in {m.value for m in PaymentMethod}:
            raise ValueError("payment_method no es válido")
        if self.payment_method == PaymentMethod.FIXED_DATE.value:
            if self.fixed_payment_day is None:
                raise ValueError("fixed_payment_day es requerido cuando payment_method es 'dia_fijo'")
            if not (1 <= self.fixed_payment_day <= 31):
                raise ValueError("fixed_payment_day debe estar entre 1 y 31")
        else:
            self.fixed_payment_day = None
        return self


class LoanCreate(LoanTerms):
    # El servidor asigna el número real (route.loans_number + 1); el valor del cliente se ignora.
    loan_number: Optional[int] = None
    initial_date: Optional[datetime] = None
    # La fecha final la fija el servidor: vencimiento de la última cuota (se ignora lo que mande el cliente).
    end_date: Optional[datetime] = None
    # Se recalculan en el servidor (cuota × cuotas, utilidad, interés); se aceptan por compatibilidad con el front.
    value_utility_loan: Optional[float] = None
    value_total_loan: Optional[float] = None
    interest_rate: Optional[float] = None
    current_address: str
    current_mobile: str
    clientroute_id: UUID
    client_id: UUID
    new_order: Optional[int] = None

    @model_validator(mode="after")
    def default_initial_date(self):
        if self.initial_date is None:
            self.initial_date = self.date_first_quota
        return self

class LoanUpdate(BaseModel):
    id: UUID
    loan_number: int
    initial_date: datetime
    end_date: datetime
    value_quota_fixed: float
    agreed_quotas: int
    date_first_quota: datetime
    payment_method: str
    fixed_payment_day: Optional[int] = None
    value_capital: float
    value_utility_loan: float
    value_total_loan: float
    interest_rate: float
    clientroute_id: UUID

class LoansFilters(BaseModel):
    text: str
    route_id: UUID
    initial_date: datetime
    end_date: datetime
    payment_method: str
