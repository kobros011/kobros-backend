from dataclasses import dataclass
from .base import Base
from typing import Optional
from datetime import datetime
from uuid import UUID

@dataclass
class Payment(Base):
    pay_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    quota_number: int = ""
    value: float = ""
    credit_value: float = ""
    applied: float = ""
    status: str = ""
    liquidated: bool = False
    date_liquidated: Optional[datetime] = None
    loan_id: UUID = None