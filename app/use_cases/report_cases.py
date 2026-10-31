from uuid import UUID
from typing import Optional, List
from app.infrastructure.repositories.report_repository import ReportRepository


class ReportUseCases:
    def __init__(self, repository: ReportRepository):
        self.repository = repository

    async def get_portfolio(
        self,
        route_id: Optional[UUID] = None,
        brand_id: Optional[UUID] = None,
    ) -> List[dict]:
        return await self.repository.get_portfolio(route_id=route_id, brand_id=brand_id)

    async def get_delinquency(
        self,
        route_id: Optional[UUID] = None,
        brand_id: Optional[UUID] = None,
    ) -> List[dict]:
        return await self.repository.get_delinquency(route_id=route_id, brand_id=brand_id)

    async def get_client_payment_history(self, client_id: UUID) -> List[dict]:
        return await self.repository.get_client_payment_history(client_id)
