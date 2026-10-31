from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.expense import Expense, ExpenseConcept
from typing import Optional, List
from app.infrastructure.models.expense_model import ExpenseModel, ExpenseConceptModel
from sqlalchemy import inspect
from app.presentation.shemas.expense_shema import ExpenseFilters

class AbstractExpenseConceptRepository(ABC):
    @abstractmethod
    async def get_expense_concept_by_id(self, concept_id: UUID) -> Optional[ExpenseConcept]:
        pass

    @abstractmethod
    async def list_expense_concepts(self) -> List[ExpenseConcept]:
        pass

    @abstractmethod
    async def create_expense_concept(self, concept: ExpenseConcept) -> Optional[ExpenseConcept]:
        pass

    @abstractmethod
    async def update_expense_concept(self, concept: ExpenseConcept) -> Optional[ExpenseConcept]:
        pass

    @abstractmethod
    async def delete_expense_concept(self, concept_id: UUID):
        pass

    @staticmethod
    def model_to_entity(model: ExpenseConceptModel) -> ExpenseConcept:
        return ExpenseConcept(
            id=model.id,
            concept=model.concept,
            keyIcon=model.keyIcon,
            color=model.color,
            brand_id=model.brand_id,
        )
    @staticmethod
    def entity_to_model(entity: ExpenseConcept) -> ExpenseConceptModel:
        return ExpenseConceptModel(
            id=entity.id,
            concept=entity.concept,
            keyIcon=entity.keyIcon,
            color=entity.color,
            brand_id=entity.brand_id,
        )
    
    @staticmethod
    def update_values(update_data: dict[str, any], current_model: ExpenseModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model

class AbstractExpenseRepository(ABC):
    @abstractmethod
    async def get_expense_by_id(self, expense_id: UUID) -> Optional[Expense]:
        pass

    @abstractmethod
    async def list_expenses(self, filters: ExpenseFilters) -> List[Expense]:
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
        state = inspect(model)

        return Expense( 
            id=model.id,
            date=model.date,
            value=model.value,
            name=model.name,
            expensesconcept_id=model.expensesconcept_id,
            user_generated=model.user_generated,
            expenseconcept=AbstractExpenseConceptRepository.model_to_entity(model.expensesconcept) if 'expensesconcept' not in state.unloaded else None,
            route_id=model.route_id,
            liquidated=model.liquidated,
            date_liquidated=model.date_liquidated,
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
            expensesconcept_id=entity.expensesconcept_id,
            user_generated=entity.user_generated,
            route_id=entity.route_id,
            liquidated=entity.liquidated,
            date_liquidated=entity.date_liquidated,
            active=entity.active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def update_values(update_data: dict[str, any], current_model: ExpenseModel):
        for key, value in update_data.items():
            setattr(current_model, key, value)

        return current_model
