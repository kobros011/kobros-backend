from typing import Optional
from uuid import UUID

from app.core.clock import today_bogota
from app.core.pagination import PaginationParams, build_page
from app.infrastructure.models.user_model import UserModel
from app.infrastructure.repositories.payment_history_repository import PaymentHistoryRepository
from app.presentation.shemas.payment_history_shema import PaymentHistoryPage


class PaymentHistoryUseCases:
    def __init__(self, repository: PaymentHistoryRepository, user: UserModel):
        self.repository = repository
        self.user = user

    def _brand_id(self) -> Optional[UUID]:
        """Solo el dev (01) ve créditos de cualquier marca; el resto, solo los de la suya."""
        role = self.user.type_user.value if hasattr(self.user.type_user, "value") else str(self.user.type_user)
        return None if role == "01" else self.user.brand_id

    async def history(self, loan_id: UUID, status: Optional[str], params: PaginationParams) -> PaymentHistoryPage:
        items, total, summary = await self.repository.history(loan_id, self._brand_id(), today_bogota(), status, params)
        page = build_page(items, total, params)
        return PaymentHistoryPage(**page.model_dump(), summary=summary)
