from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class BrandRead(BaseModel):
    id: UUID
    name: str
    code: str
    loans_number: int
    created_at: datetime
    updated_at: datetime
    active: bool

class BrandCreate(BaseModel):
    name: str
    code: str
    loans_number: int

class BrandUpdate(BaseModel):
    id: UUID
    name: str
    code: str