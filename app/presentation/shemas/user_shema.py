from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    password: str
    name: str = ""
    last_name: str = ""
    type_user: str
    brand_id: UUID | None = None


class UserRead(BaseModel):
    id: UUID
    username: str
    name: str
    last_name: str
    type_user: str
    created_at: datetime
    updated_at: datetime
    active: bool

    class Comfig:
        orm_mode = True


class UserUpdate(BaseModel):
    id: UUID
    username: str
    name: str
    last_name: str
    type_user: str
