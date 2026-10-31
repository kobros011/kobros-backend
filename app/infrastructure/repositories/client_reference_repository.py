from uuid import UUID
from typing import List
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.infrastructure.models.client_reference_model import ClientReferenceModel
from app.domain.entities.client_reference import ClientReference
from app.infrastructure.utils.validator_errors import ValidatorErrors
from app.core.exceptions import ConflictException


class ClientReferenceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_client(self, client_id: UUID) -> List[ClientReference]:
        result = await self.db.execute(
            select(ClientReferenceModel).where(ClientReferenceModel.client_id == client_id)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def replace_for_client(self, client_id: UUID, references: List[dict]) -> List[ClientReference]:
        try:
            existing = await self.db.execute(
                select(ClientReferenceModel).where(ClientReferenceModel.client_id == client_id)
            )
            for model in existing.scalars().all():
                await self.db.delete(model)

            new_models = []
            for ref in references:
                model = ClientReferenceModel(
                    name=ref.get("name", ""),
                    address=ref.get("address", ""),
                    phone=ref.get("phone", ""),
                    client_id=client_id,
                )
                self.db.add(model)
                new_models.append(model)

            await self.db.flush()
            return [self._to_entity(m) for m in new_models]

        except IntegrityError as e:
            await self.db.rollback()
            raise ConflictException(ValidatorErrors.integrity_error(e))

    @staticmethod
    def _to_entity(model: ClientReferenceModel) -> ClientReference:
        return ClientReference(
            id=model.id,
            name=model.name,
            address=model.address,
            phone=model.phone,
            client_id=model.client_id,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
