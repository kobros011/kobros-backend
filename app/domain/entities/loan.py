from dataclasses import dataclass
from app.domain.entities.base import Base
from uuid import UUID
from typing import Optional
from datetime import datetime

@dataclass
class Loan(Base):
    loan_number: int = 0
    initial_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    value_quota_fixed: float = ""
    agreed_quotas: int = 0
    date_first_quota: Optional[datetime] = None
    payment_method: str = ""
    fixed_payment_day: Optional[int] = None
    value_capital: float = ""
    value_utility_loan: float = ""
    value_total_loan: float = ""
    interest_rate: float = ""
    pending_quotas: int = 0
    canceled_quotas: int = 0
    total_default: float | None = None

    clientroute_id: UUID = None

@dataclass
class LoanFull(Loan):
    client_fullname: str = ""
    client_id: UUID = None
    client_id_document: str = ""
    client_current_address: str = ""
    client_current_mobile: str = ""
    route_name: str = ""
    route_id: UUID = None
    order: int = 0