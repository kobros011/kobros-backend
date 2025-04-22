from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class ClientRead(BaseModel):
    id: UUID
    full_name: str
    id_document: str
    current_address: str
    current_phone: str
    brand_id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime

class ClientCreate(BaseModel):
    full_name: str
    id_document: str
    current_address: str
    current_phone: str
    brand_id: UUID

class ClientUpdate(BaseModel):
    id: UUID
    full_name: str
    id_document: str
    current_address: str
    current_phone: str
