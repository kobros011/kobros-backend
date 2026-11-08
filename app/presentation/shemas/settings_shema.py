from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

NumberFormatStyle = Literal["comma-thousands", "dot-thousands"]
LogoTone = Literal["dark", "light", "mixed"]
LogoVariant = Literal["full", "mark"]


class SettingsRead(BaseModel):
    brand_id: Optional[UUID] = None
    brand_name: Optional[str] = None
    brand_code: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    app_name: Optional[str] = None
    primary_color: Optional[str] = None
    # Logo del menú expandido / login.
    logo_full_url: Optional[str] = None
    logo_full_width: Optional[int] = None
    logo_full_height: Optional[int] = None
    logo_full_tone: Optional[LogoTone] = None
    # Logo (o ícono) del menú colapsado — independiente del anterior, el cliente decide si lo sube.
    logo_mark_url: Optional[str] = None
    logo_mark_width: Optional[int] = None
    logo_mark_height: Optional[int] = None
    logo_mark_tone: Optional[LogoTone] = None
    number_format_style: NumberFormatStyle = "comma-thousands"
    number_decimals: Literal[0, 2] = 2
    # Monedas de la marca (códigos ISO); la primera es la principal. Vacío = sin configurar.
    currencies: List[str] = []
    # Falso si Azure no está configurado: el front deshabilita la subida de logo.
    logo_enabled: bool = False


class SettingsUpdate(BaseModel):
    brand_name: Optional[str] = Field(default=None, max_length=80)
    brand_code: Optional[str] = Field(default=None, max_length=20)
    contact_email: Optional[str] = Field(default=None, max_length=120)
    contact_phone: Optional[str] = Field(default=None, max_length=40)
    app_name: Optional[str] = Field(default=None, max_length=40)
    primary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    number_format_style: NumberFormatStyle = "comma-thousands"
    number_decimals: Literal[0, 2] = 2
    currencies: Optional[List[str]] = None  # None = no tocar las monedas

    @field_validator("currencies", mode="before")
    @classmethod
    def _normalize_currencies(cls, value):
        if value is None:
            return None
        return list(dict.fromkeys(str(code).strip().upper() for code in value if str(code).strip()))

    @field_validator("primary_color", mode="before")
    @classmethod
    def _blank_color(cls, value):
        return value.strip().lower() if isinstance(value, str) and value.strip() else None

    @field_validator("contact_email", "contact_phone", "app_name", "brand_name", "brand_code")
    @classmethod
    def _blank_to_none(cls, value: Optional[str]) -> Optional[str]:
        value = (value or "").strip()
        return value or None
