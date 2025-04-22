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
    value_capital: float = ""
    value_utility_loan: float = ""
    value_total_loan: float = ""
    interest_rate: float = ""

    clientroute_id = UUID = None
