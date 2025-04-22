from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class LoanRead(BaseModel):
    id: UUID
    loan_number: int
    initial_date: datetime
    end_date: datetime
    value_quota_fixed:float 
    agreed_quotas: int
    date_first_quota: datetime
    payment_method: str
    value_capital: float
    value_utility_loan: float
    value_total_loan: float
    interest_rate: float
    clientroute_id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime

class LoanCreate(BaseModel):
    loan_number: int
    initial_date: datetime
    end_date: datetime
    value_quota_fixed:float 
    agreed_quotas: int
    date_first_quota: datetime
    payment_method: str
    value_capital: float
    value_utility_loan: float
    value_total_loan: float
    interest_rate: float
    clientroute_id: UUID

class LoanUpdate(BaseModel):
    id: UUID
    loan_number: int
    initial_date: datetime
    end_date: datetime
    value_quota_fixed:float 
    agreed_quotas: int
    date_first_quota: datetime
    payment_method: str
    value_capital: float
    value_utility_loan: float
    value_total_loan: float
    interest_rate: float
    clientroute_id: UUID
