from dataclasses import dataclass
from math import ceil
from typing import Any, Callable, Generic, List, Optional, Sequence, TypeVar, Union

from fastapi import Query, Request
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


def optional_pagination_params(
    page: Optional[int] = Query(None, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> Optional[PaginationParams]:
    """Paginación opt-in: sin `page` el endpoint conserva su respuesta plana de siempre."""
    if page is None:
        return None
    return PaginationParams(page=page, page_size=page_size)


def filters_from_request(request: Request) -> dict:
    return {k: v for k, v in request.query_params.items() if k not in ("page", "page_size")}


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


async def paginate_or_all(
    db: AsyncSession,
    stmt: Select,
    params: Optional[PaginationParams],
    mapper: Callable[[Any], T],
) -> tuple[List[T], int]:
    if params is None:
        rows = (await db.execute(stmt)).scalars().all()
        return [mapper(row) for row in rows], len(rows)

    rows, total = await paginate(db, stmt, params)
    return [mapper(row) for row in rows], total


async def paginate_mappings(
    db: AsyncSession,
    stmt: Select,
    params: Optional[PaginationParams],
) -> tuple[List[dict], int]:
    """Pagina un select de columnas (no de entidades ORM): cuenta sobre subquery y devuelve dicts.

    Sin `params` devuelve todas las filas (respuesta plana opt-in, igual que `paginate_or_all`).
    """
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    if params is not None:
        stmt = stmt.offset(params.offset).limit(params.page_size)

    rows = (await db.execute(stmt)).mappings().all()
    return [dict(row) for row in rows], (total if params is not None else len(rows))


def build_page(items: List[T], total: int, params: PaginationParams) -> Page[T]:
    pages = ceil(total / params.page_size) if params.page_size else 0
    return Page[T](items=items, total=total, page=params.page, page_size=params.page_size, pages=pages)


def page_or_list(items: List[T], total: int, params: Optional[PaginationParams]) -> Union[Page[T], List[T]]:
    return items if params is None else build_page(items, total, params)
