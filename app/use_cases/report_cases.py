from uuid import UUID
from typing import Optional, List, Union
from app.infrastructure.repositories.report_repository import ReportRepository
from app.infrastructure.models.user_model import UserModel
from app.core.pagination import PaginationParams, Page, page_or_list


def _role(user: UserModel) -> str:
    return user.type_user.value if hasattr(user.type_user, "value") else str(user.type_user)


class ReportUseCases:
    user: Optional[UserModel] = None

    def __init__(self, repository: ReportRepository):
        self.repository = repository

    def _effective_brand_id(self, requested_brand_id: Optional[UUID]) -> Optional[UUID]:
        """El dev (01) puede filtrar libremente por marca; cualquier otro rol queda fijo en la suya,
        sin importar lo que mande el cliente — evita que un query ajeno filtre otras marcas."""
        if self.user and _role(self.user) == "01":
            return requested_brand_id
        return self.user.brand_id if self.user else requested_brand_id

    @staticmethod
    def _route_ids(route_id: Optional[UUID]) -> Optional[List[UUID]]:
        return [route_id] if route_id else None

    async def get_portfolio(
        self,
        route_id: Optional[UUID] = None,
        brand_id: Optional[UUID] = None,
        text: Optional[str] = None,
        params: Optional[PaginationParams] = None,
        currency: Optional[str] = None,
    ) -> Union[Page[dict], List[dict]]:
        items, total = await self.repository.list_portfolio(self._route_ids(route_id), self._effective_brand_id(brand_id), text, params, currency)
        return page_or_list(items, total, params)

    async def get_delinquency(
        self,
        route_id: Optional[UUID] = None,
        brand_id: Optional[UUID] = None,
        text: Optional[str] = None,
        params: Optional[PaginationParams] = None,
        currency: Optional[str] = None,
    ) -> Union[Page[dict], List[dict]]:
        items, total = await self.repository.list_delinquency(self._route_ids(route_id), self._effective_brand_id(brand_id), text, params, currency)
        return page_or_list(items, total, params)

    async def get_portfolio_summary(self, route_id: Optional[UUID] = None, brand_id: Optional[UUID] = None, text: Optional[str] = None, currency: Optional[str] = None) -> dict:
        return await self.repository.portfolio_summary(self._route_ids(route_id), self._effective_brand_id(brand_id), text, currency)

    async def get_delinquency_summary(self, route_id: Optional[UUID] = None, brand_id: Optional[UUID] = None, text: Optional[str] = None, currency: Optional[str] = None) -> dict:
        return await self.repository.delinquency_summary(self._route_ids(route_id), self._effective_brand_id(brand_id), text, currency)

    async def get_client_payment_history(self, client_id: UUID) -> List[dict]:
        return await self.repository.get_client_payment_history(client_id)
