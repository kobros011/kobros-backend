from datetime import date
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

from ...core.pagination import Page

HistoryStatus = Literal["pagado", "pendiente", "mora"]


class PaymentHistoryRead(BaseModel):
    id: UUID
    quota_number: int
    pay_date: date
    payment_date: Optional[date] = None
    value: float
    applied: float
    balance: float
    excess: float
    status: HistoryStatus
    days_overdue: int
    paid_late_days: int
    collected_by_id: Optional[UUID] = None
    collected_by_name: Optional[str] = None
    can_pay: bool


class PaymentHistorySummary(BaseModel):
    total_quotas: int
    paid: int
    pending: int
    overdue: int
    total_due: float
    total_paid: float
    total_balance: float
    paid_percent: float


class PaymentHistoryPage(Page[PaymentHistoryRead]):
    summary: PaymentHistorySummary
