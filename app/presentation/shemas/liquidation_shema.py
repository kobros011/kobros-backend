from datetime import date as date_type
from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

LiquidationStatus = Literal["pendiente", "confirmada", "reabierta"]


class LiquidationCreate(BaseModel):
    """El servidor calcula recaudo, gastos, créditos nuevos, meta, esperado y diferencia; aquí solo lo que digita quien cierra."""
    route_id: UUID
    date: date_type
    value_base_delivered: float = Field(ge=0)
    cash_delivered: float = Field(ge=0)
    note: Optional[str] = Field(None, max_length=500)
    # Solo admin: cierra a nombre de un cobrador (vacío = consolidado de la ruta). El cobrador siempre cierra el suyo.
    collector_id: Optional[UUID] = None


class LiquidationNoteUpdate(BaseModel):
    note: Optional[str] = Field(None, max_length=500)


class ExpenseLine(BaseModel):
    id: UUID
    name: str
    concept: Optional[str] = None
    value: float


class PaymentLine(BaseModel):
    id: UUID
    client_name: str
    loan_number: int
    quota_number: int
    pay_date: date_type
    value: float
    applied: float


class NewLoanLine(BaseModel):
    id: UUID
    loan_number: int
    client_name: str
    value_capital: float
    value_total_loan: float
    agreed_quotas: int
    value_quota_fixed: float
    payment_method: str


class ClosingFigures(BaseModel):
    goal: float
    collected_total: float
    receipts_count: int
    collected_due_today: float
    collected_overdue: float
    partial_count: int
    beak_generated: float
    expenses_total: float
    new_loans_total: float
    new_loans_count: int


class LiquidationPreviewRead(ClosingFigures):
    route_id: UUID
    route_name: str
    collector_id: Optional[UUID] = None
    collector_name: Optional[str] = None
    date: date_type
    suggested_base: float
    expected_cash: float
    progress_percent: float
    expenses: List[ExpenseLine]
    new_loans: List[NewLoanLine]
    existing_liquidation_id: Optional[UUID] = None
    existing_status: Optional[LiquidationStatus] = None


class LiquidationRead(BaseModel):
    id: UUID
    date: date_type
    route_id: UUID
    route_name: str
    collector_id: Optional[UUID] = None
    collector_name: Optional[str] = None
    today_collection_goal: float
    value_base_delivered: float
    total_value_charged: float
    total_value_expenses: float
    value_new_loans: float
    cash_delivered: Optional[float] = None
    expected_cash: Optional[float] = None
    difference: Optional[float] = None
    receipts_count: int = 0
    beak_generated: float = 0
    note: Optional[str] = None
    status: LiquidationStatus
    admin_confirmed_at: Optional[datetime] = None
    admin_confirmed_by: Optional[UUID] = None
    confirmed_by_name: Optional[str] = None
    reopened_at: Optional[datetime] = None
    active: bool
    created_at: datetime


class LiquidationDetailRead(LiquidationRead):
    outdated: bool
    current_total_charged: float
    current_total_expenses: float
    current_new_loans: float
    payments: List[PaymentLine]
    expenses: List[ExpenseLine]
    new_loans: List[NewLoanLine]
