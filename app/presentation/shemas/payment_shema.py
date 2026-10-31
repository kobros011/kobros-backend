from typing import Optional
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class PaymentRead(BaseModel):
    id: UUID
    pay_date: datetime
    payment_date: datetime | None = None
    quota_number: int 
    value: float
    credit_value: float
    status: str
    loan_id: UUID
    liquidated: bool = False
    date_liquidated: Optional[datetime] = None
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]

class PaymentFullRead(PaymentRead):
    pending_quotas: int
    canceled_quotas: int
    agreed_quotas: int
    total_default: float | None = None
    value_capital: float
    value_quota_fixed: float
    payment_method: str
    value_total_loan: float
    applied: float | None = None
    client_id: UUID
    route_id: UUID
    client_full_name: str

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

class CollectionTodayRead(PaymentFullRead):
    order: int
    id_document: str
    client_address: Optional[str] = None
    client_mobile: Optional[str] = None
    loan_number: int

class PaymentFilters(BaseModel):
    text: str
    status: str
    route_id: UUID
    pay_date: str
    payment_date: str
    date_liquidated: datetime
    payments_to_pay: bool
    payments_to_pay_today: bool
    payments_pending: bool
