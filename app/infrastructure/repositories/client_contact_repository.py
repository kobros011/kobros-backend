from typing import List
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.exceptions import ConflictException
from app.infrastructure.models.client_contact_model import ClientContactModel
from app.infrastructure.utils.validator_errors import ValidatorErrors


class ClientContactRepository:
    """Fiadores y referencias del cliente. Se reemplaza la lista completa; `position` (1 = principal) se calcula por tipo."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def replace_for_client(self, client_id: UUID, contacts: List[dict]) -> List[ClientContactModel]:
        try:
            existing = await self.db.execute(select(ClientContactModel).where(ClientContactModel.client_id == client_id))
            for model in existing.scalars().all():
                await self.db.delete(model)
            await self.db.flush()

            counters: dict[str, int] = {}
            new_models = []
            for contact in contacts:
                kind = contact["kind"]
                counters[kind] = counters.get(kind, 0) + 1
                model = ClientContactModel(
                    client_id=client_id,
                    kind=kind,
                    name=contact["name"],
                    phone=contact["phone"],
                    address=contact.get("address") or None,
                    position=counters[kind],
                )
                self.db.add(model)
                new_models.append(model)

            await self.db.flush()
            return new_models
        except IntegrityError as e:
            await self.db.rollback()
            raise ConflictException(ValidatorErrors.integrity_error(e))
