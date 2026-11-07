from dataclasses import dataclass
from math import ceil
from typing import Generic, List, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.sql import Select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


@dataclass
class PaginationParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int


async def paginate(db: AsyncSession, stmt: Select, params: PaginationParams) -> tuple[Sequence, int]:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    page_stmt = stmt.offset(params.offset).limit(params.page_size)
    rows = (await db.execute(page_stmt)).scalars().all()

    return rows, total


def build_page(items: List[T], total: int, params: PaginationParams) -> Page[T]:
    pages = ceil(total / params.page_size) if params.page_size else 0
    return Page[T](items=items, total=total, page=params.page, page_size=params.page_size, pages=pages)
