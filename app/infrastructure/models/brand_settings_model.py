from sqlalchemy import JSON, Column, String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PD_UUID
from app.infrastructure.dababase.base_class import Base


class BrandSettingsModel(Base):
    """Configuración (white label + formato de números) de una marca. 1:1 con brands.

    El logo tiene dos ranuras independientes, cada una con su propio archivo: `full` (menú
    expandido / login) y `mark` (menú colapsado). El cliente decide si sube una, otra o ambas —
    no están atadas entre sí.
    """

    __tablename__ = "brand_settings"

    brand_id = Column(PD_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    app_name = Column(String, nullable=True)
    primary_color = Column(String, nullable=True)

    # Nombre del blob en Azure (no la URL: la URL firmada se genera al leer).
    logo_full_blob = Column(String, nullable=True)
    logo_full_width = Column(Integer, nullable=True)
    logo_full_height = Column(Integer, nullable=True)
    logo_full_tone = Column(String, nullable=True)  # "dark" | "light" | "mixed"

    logo_mark_blob = Column(String, nullable=True)
    logo_mark_width = Column(Integer, nullable=True)
    logo_mark_height = Column(Integer, nullable=True)
    logo_mark_tone = Column(String, nullable=True)  # "dark" | "light" | "mixed"

    number_format_style = Column(String, nullable=False, default="comma-thousands", server_default="comma-thousands")
    number_decimals = Column(Integer, nullable=False, default=2, server_default="2")
    # Códigos ISO de las monedas de la marca; la primera es la principal. Vacío = sin configurar (no hay moneda por defecto).
    currencies = Column(JSON, nullable=False, default=list, server_default="[]")
