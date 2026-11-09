from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.dababase.base_class import Base

CONTACT_KINDS = ("fiador", "referencia")


class ClientContactModel(Base):
    """Fiador o referencia de un cliente. Un cliente puede tener varios de cada tipo; `position` 1 es el principal."""

    __tablename__ = "client_contacts"
    __table_args__ = (CheckConstraint("kind IN ('fiador', 'referencia')", name="ck_client_contacts_kind"),)

    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String, nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    address = Column(String, nullable=True)
    position = Column(Integer, nullable=False, default=1)

    client = relationship("ClientModel", back_populates="contacts")
