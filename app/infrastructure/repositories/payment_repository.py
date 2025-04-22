from uuid import UUID
from ...domain.entities.payment import Payment
from ...domain.repositories.payment_repository import AbstractPaymentRepository
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.payment_model import PaymentModel
from ...presentation.shemas.payment_shema import PaymentUpdate
from ..utils.validator_errors import ValidatorErrors
from ...core.exceptions import ConflictException, NotFoundException

class PaymentRepository(AbstractPaymentRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
 
    async def get_payment_by_id(self, payment_id: UUID) -> Optional[Payment]:
        try:
            result = await self.db.execute(
                select(PaymentModel).where(PaymentModel.id == payment_id)
            )
            model = result.scalars().first()

            if not model:
                raise NotFoundException("El pago no fue encontrado")
            return self.model_to_entity(model)
            
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def list_payments(self) -> List[Payment]:
        try:
            result = await self.db.execute(select(PaymentModel))
            models = result.scalars().all()
            return [self.model_to_entity(m) for m in models]
        except IntegrityError as e:
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def create_payment(self, payment: Payment) -> Optional[Payment]:
        try:
            orm_payment = self.entity_to_model(payment)
            self.db.add(orm_payment)
            await self.db.commit()
            await self.db.refresh(orm_payment)
            return self.model_to_entity(orm_payment)
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

    async def update_payment(self, payment: PaymentUpdate) -> Optional[Payment]:
        try:
            result = await self.db.execute(
                select(PaymentModel).where(PaymentModel.id == payment.id)
            )
            current_payment = result.scalars().first()

            if not current_payment:
                raise NotFoundException("El pago no fue encontrado")

            update_data = payment.model_dump(exclude_unset=True)

            current_payment = self.update_values(update_data, current_model=current_payment)

            await self.db.commit()
            await self.db.refresh(current_payment)
            return self.model_to_entity(current_payment)

        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

        
    async def delete_payment(self, payment_id:UUID):
        try:
            result = await self.db.execute(
                select(PaymentModel).where(PaymentModel.id == payment_id)
            )
            current_payment = result.scalars().first()

            if not current_payment:
                raise NotFoundException("El pago no fue encontrado")
            
            current_payment.active = False

            await self.db.commit()
            await self.db.refresh(current_payment)
            return "Pago eliminado exitosamente"
        
        except IntegrityError as e:
            await self.db.rollback()
            user_message = ValidatorErrors.integrity_error(e)
            raise ConflictException(user_message)

