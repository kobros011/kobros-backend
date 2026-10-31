from pydantic import BaseModel, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

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

class LoanCreate(BaseModel):
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
    current_address: str
    current_mobile: str
    clientroute_id: UUID
    client_id: UUID
    new_order: int = None

    @model_validator(mode="after")
    def validate_fixed_date(self):
        if self.payment_method == "dia_fijo":
            if self.fixed_payment_day is None:
                raise ValueError("fixed_payment_day es requerido cuando payment_method es 'dia_fijo'")
            if not (1 <= self.fixed_payment_day <= 31):
                raise ValueError("fixed_payment_day debe estar entre 1 y 31")
        else:
            self.fixed_payment_day = None
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
