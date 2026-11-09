from uuid import UUID
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional

from app.utils.user_credentials import normalize_email, validate_email_optional, validate_password, validate_username


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    document_id: str
    linking_date: Optional[datetime]
    address: Optional[str] = ''
    phone: Optional[str] = ''
    mobile: Optional[str] = ''
    city: Optional[str] = ''
    department: Optional[str] = ''
    type_user: str
    brand_id: Optional[UUID] = None
    email: Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_user_email(cls, value):
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str):
        err = validate_password(value)
        if err:
            raise ValueError(err)
        return value

    @field_validator("username")
    @classmethod
    def check_username(cls, value: str):
        err = validate_username(value)
        if err:
            raise ValueError(err)
        return value

    @field_validator("email")
    @classmethod
    def check_email(cls, value: Optional[str]):
        err = validate_email_optional(value)
        if err:
            raise ValueError(err)
        return value


class UserRead(BaseModel):
    id: UUID
    username: str
    email: Optional[str] = None
    full_name: str
    document_id: str
    linking_date: Optional[datetime]
    address: Optional[str]
    phone: Optional[str]
    mobile: Optional[str]
    city: Optional[str]
    department: Optional[str]
    type_user: str
    brand_id: UUID | None
    has_clerk_account: bool = False
    created_at: datetime
    updated_at: Optional[datetime]
    active: bool


class UserRouteRead(BaseModel):
    """Ruta de la marca del usuario y si está asignado; los pendientes solo cuentan en las asignadas."""
    route_id: UUID
    name: str
    currency: str
    active: bool
    assigned: bool
    pending_payments: int = 0
    open_liquidations: int = 0


class UserRouteRemoved(BaseModel):
    removed: bool
    pending_payments: int = 0
    open_liquidations: int = 0


class UserUpdate(BaseModel):
    id: UUID
    username: str
    full_name: str
    document_id: str
    linking_date: Optional[datetime] = None
    address: Optional[str] = ''
    phone: Optional[str] = ''
    mobile: Optional[str] = ''
    city: Optional[str] = ''
    department: Optional[str] = ''
    type_user: str
    email: Optional[str] = None
    brand_id: Optional[UUID] = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_user_email(cls, value):
        return normalize_email(value)

    @field_validator("username")
    @classmethod
    def check_username(cls, value: str):
        err = validate_username(value)
        if err:
            raise ValueError(err)
        return value

    @field_validator("email")
    @classmethod
    def check_email(cls, value: Optional[str]):
        err = validate_email_optional(value)
        if err:
            raise ValueError(err)
        return value


class UserPasswordUpdate(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str):
        err = validate_password(value)
        if err:
            raise ValueError(err)
        return value


class UserFilters(BaseModel):
    active: bool
    text: str


def user_to_read(user) -> UserRead:
    type_user = user.type_user.value if hasattr(user.type_user, "value") else str(user.type_user)
    return UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name or "",
        document_id=user.document_id or "",
        linking_date=user.linking_date,
        address=user.address,
        phone=user.phone,
        mobile=user.mobile,
        city=user.city,
        department=user.department,
        type_user=type_user,
        brand_id=user.brand_id,
        has_clerk_account=bool(user.clerk_user_id),
        created_at=user.created_at,
        updated_at=user.updated_at,
        active=user.active,
    )
