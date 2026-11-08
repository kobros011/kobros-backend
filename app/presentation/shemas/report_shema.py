from pydantic import BaseModel
from uuid import UUID
from datetime import date
from typing import Optional, List


class PortfolioItemRead(BaseModel):
    client_id: UUID
    client_name: str
    loan_id: UUID
    loan_number: int
    route_id: UUID
    route_name: str
    value_total_loan: float
    total_paid: float
    balance: float
    end_date: date
    payment_method: str


class DelinquencyItemRead(BaseModel):
    client_id: UUID
    client_name: str
    loan_id: UUID
    loan_number: int
    route_id: UUID
    route_name: str
    value_total_loan: float
    total_paid: float
    balance: float  # saldo en mora = suma de las cuotas vencidas impagas
    end_date: date
    days_overdue: int
    loan_balance: float
    overdue_quotas: int
    overdue_since: date


class PaymentHistoryItemRead(BaseModel):
    payment_id: UUID
    loan_id: UUID
    loan_number: int
    quota_number: int
    pay_date: date
    payment_date: Optional[date]
    value: float
    applied: float
    status: str


class ReportSummaryRead(BaseModel):
    total_balance: float
    count: int
