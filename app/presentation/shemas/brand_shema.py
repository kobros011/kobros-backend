from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class BrandRead(BaseModel):
    id: UUID
    name: str
    code: str
    routes_available: int
    created_at: datetime
    updated_at: Optional[datetime]
    active: bool


class BrandCreate(BaseModel):
    name: str
    code: str
    routes_available: int


class BrandUpdate(BaseModel):
    id: UUID
    name: str
    code: str
    routes_available: int


class BrandFilters(BaseModel):
    active: bool
    text: str

