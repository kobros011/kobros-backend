from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.expense import Expense
from typing import Optional, List
from app.infrastructure.models.expense_model import ExpenseModel


class AbstractExpenseRepository(ABC):
    @abstractmethod
    async def get_expense_by_id(self, expense_id: UUID) -> Optional[Expense]:
        pass

    @abstractmethod
    async def list_expenses(self) -> List[Expense]:
        pass

    @abstractmethod
    async def create_expense(self, expense: Expense) -> Optional[Expense]:
        pass

    @abstractmethod
    async def update_expense(self, expense: Expense) -> Optional[Expense]:
        pass

    @abstractmethod
    async def delete_expense(self, expense_id: UUID):
        pass

    @staticmethod
    def model_to_entity(model: ExpenseModel) -> Expense:
        return Expense( 
            id=model.id,
            date=model.date,
            value=model.value,
            name=model.name,
            type=model.type,
            concept=model.concept,
            route_id=model.route_id,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def entity_to_model(entity: Expense) -> ExpenseModel:
        return ExpenseModel(
            id=entity.id,
            date=entity.date,
            value=entity.value,
            name=entity.name,
            type=entity.type,
            concept=entity.concept,
            route_id=entity.route_id,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def update_values(update_data: dict[str, any], current_model: ExpenseModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model
