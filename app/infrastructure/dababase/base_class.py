from sqlalchemy import Column, Boolean, func, DateTime
from sqlalchemy.dialects.postgresql import UUID as PD_UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy.ext.asyncio import AsyncAttrs
import uuid


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True

    @declared_attr
    def id(cls):
        return Column(PD_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    @declared_attr
    def active(cls):
        return Column(Boolean, default=True)

    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), server_default=func.now())

    @declared_attr
    def updated_at(cls):
        return Column(DateTime(timezone=True), onupdate=func.now())
