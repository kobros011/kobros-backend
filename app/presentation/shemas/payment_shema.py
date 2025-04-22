from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class PaymentRead(BaseModel):
    id: UUID
    pay_date: datetime
    payment_date: datetime
    quota_number: int 
    value: float
    credit_value: float
    status: str
    loan_id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime

class PaymentCreate(BaseModel):
    pay_date: datetime
    payment_date: datetime
    quota_number: int 
    value: float
    credit_value: float
    status: str
    loan_id: UUID

class PaymentUpdate(BaseModel):
    id: UUID
    pay_date: datetime
    payment_date: datetime
    quota_number: int 
    value: float
    credit_value: float
    status: str
