from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.client import Client, ClientById
from typing import Optional, List
from app.infrastructure.models.client_model import ClientModel, RouteInfo
from app.infrastructure.models.user_model import UserModel
from app.core.pagination import PaginationParams
from app.presentation.shemas.client_shema import ClientCreate, ClientUpdate
from .client_route_repository import AbstractClientRouteRepository
from sqlalchemy import inspect


class AbstractClientRepository(ABC):
    user: Optional[UserModel] = None
    @abstractmethod
    async def get_client_by_id(self, client_id: UUID) -> Optional[Client]:
        pass

    @abstractmethod
    async def get_by_id_more_info(self, client_id: UUID) -> Optional[ClientById]:
        pass

    @abstractmethod
    async def list_clients(self, filters, params: Optional[PaginationParams] = None) -> tuple[List[Client], int]:
        pass

    @abstractmethod
    async def create_client(self, client: ClientCreate) -> Optional[Client]:
        pass

    @abstractmethod
    async def update_client(self, client: ClientUpdate) -> Optional[Client]:
        pass

    @abstractmethod
    async def toggle_client(self, client_id: UUID):
        pass

    @staticmethod
    def model_to_entity(model: ClientModel) -> Client:
        routes_ids = [AbstractClientRouteRepository.model_to_entity(m).route_id for m in model.clientsroutes]
        refs = [
            {"id": str(r.id), "name": r.name, "address": r.address, "phone": r.phone}
            for r in (model.references or [])
        ]

        return Client(
            id=model.id,
            full_name=model.full_name,
            id_document=model.id_document,
            current_address=model.current_address,
            current_phone=model.current_phone,
            neighborhood=model.neighborhood,
            current_mobile=model.current_mobile,
            linking_date=model.linking_date,
            beak=model.beak,
            active=model.active,
            routes_ids=routes_ids,
            brand_id=model.brand_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            guarantor_name=model.guarantor_name,
            guarantor_cedula=model.guarantor_cedula,
            guarantor_phone=model.guarantor_phone,
            guarantor_address=model.guarantor_address,
            references=refs,
        )

    @staticmethod
    def model_by_id_to_entity(model: ClientModel, route_id: Optional[UUID]) -> ClientById:
        more_info = model.get_route_info(route_id=route_id) if route_id else RouteInfo()
        refs = [
            {"id": str(r.id), "name": r.name, "address": r.address, "phone": r.phone}
            for r in (model.references or [])
        ]

        return ClientById(
            id=model.id,
            full_name=model.full_name,
            id_document=model.id_document,
            current_address=model.current_address,
            current_phone=model.current_phone,
            neighborhood=model.neighborhood,
            current_mobile=model.current_mobile,
            linking_date=model.linking_date,
            beak=model.beak,
            order=more_info.order,
            route_id=more_info.route_id,
            route_name=more_info.route_name,
            active=model.active,
            brand_id=model.brand_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            guarantor_name=model.guarantor_name,
            guarantor_cedula=model.guarantor_cedula,
            guarantor_phone=model.guarantor_phone,
            guarantor_address=model.guarantor_address,
            references=refs,
        )

    @staticmethod
    def entity_to_model(entity: Client) -> ClientModel:
        return ClientModel(
            full_name=entity.full_name,
            id_document=entity.id_document,
            current_address=entity.current_address,
            current_phone=entity.current_phone,
            neighborhood=entity.neighborhood,
            current_mobile=entity.current_mobile,
            linking_date=entity.linking_date,
            brand_id= entity.brand_id,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def update_values(update_data: dict[str, any], current_model: ClientModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model
