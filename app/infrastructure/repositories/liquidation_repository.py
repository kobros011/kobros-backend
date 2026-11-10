from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ...core.clock import today_bogota
from ...core.exceptions import BadRequestException, ConflictException, NotFoundException
from ...core.pagination import PaginationParams, paginate_mappings
from ..models.expense_model import ExpenseModel
from ..models.liquidation_model import LiquidationModel
from ..models.payment_model import PaymentModel
from ..models.route_model import RouteModel
from ..models.user_model import UserModel
from ..utils.validator_errors import ValidatorErrors
from . import liquidation_calculator as calc

_COLLECTOR = aliased(UserModel)
_CONFIRMER = aliased(UserModel)


def _status(row) -> str:
    if row["reopened_at"] is not None:
        return "reabierta"
    return "confirmada" if row["admin_confirmed_at"] is not None else "pendiente"


def _read_columns():
    return [
        *[c for c in LiquidationModel.__table__.c],
        RouteModel.name.label("route_name"),
        _COLLECTOR.full_name.label("collector_name"),
        _CONFIRMER.full_name.label("confirmed_by_name"),
    ]


def _read_select():
    return (
        select(*_read_columns())
        .select_from(LiquidationModel)
        .join(RouteModel, RouteModel.id == LiquidationModel.route_id)
        .outerjoin(_COLLECTOR, _COLLECTOR.id == LiquidationModel.collector_id)
        .outerjoin(_CONFIRMER, _CONFIRMER.id == LiquidationModel.admin_confirmed_by)
    )


_MONEY = ("today_collection_goal", "value_base_delivered", "total_value_charged", "total_value_expenses", "value_new_loans",
          "cash_delivered", "expected_cash", "difference", "beak_generated")


def _to_read(row) -> dict:
    data = dict(row)
    for key in _MONEY:  # las columnas Float(2, True) llegan como Decimal
        if data.get(key) is not None:
            data[key] = float(data[key])
    data["status"] = _status(data)
    return data


class LiquidationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- lecturas ----
    async def get_route(self, route_id: UUID) -> RouteModel:
        route = (await self.db.execute(select(RouteModel).where(RouteModel.id == route_id))).scalars().first()
        if route is None:
            raise NotFoundException("Ruta no encontrada")
        return route

    async def get_model(self, liquidation_id: UUID) -> LiquidationModel:
        model = (await self.db.execute(select(LiquidationModel).where(LiquidationModel.id == liquidation_id))).scalars().first()
        if model is None:
            raise NotFoundException("Liquidación no encontrada")
        return model

    async def get_read(self, liquidation_id: UUID) -> dict:
        row = (await self.db.execute(_read_select().where(LiquidationModel.id == liquidation_id))).mappings().first()
        if row is None:
            raise NotFoundException("Liquidación no encontrada")
        return _to_read(row)

    async def user_name(self, user_id: Optional[UUID]) -> Optional[str]:
        if not user_id:
            return None
        return (await self.db.execute(select(UserModel.full_name).where(UserModel.id == user_id))).scalar_one_or_none()

    async def active_for(self, route_id: UUID, day: date, collector_id: Optional[UUID]) -> Optional[dict]:
        stmt = _read_select().where(LiquidationModel.route_id == route_id, LiquidationModel.date == day, LiquidationModel.active.is_(True))
        stmt = stmt.where(LiquidationModel.collector_id == collector_id) if collector_id else stmt.where(LiquidationModel.collector_id.is_(None))
        row = (await self.db.execute(stmt)).mappings().first()
        return _to_read(row) if row else None

    async def suggested_base(self, route: RouteModel, collector_id: Optional[UUID]) -> tuple[float, str]:
        """Base sugerida y de dónde sale: la del último cierre activo de esa ruta/cobrador (`last_closure`); si nunca
        hubo uno, lo que se le entrega al cobrador al empezar: valor inicial de la ruta menos sus gastos iniciales (`route_initial`)."""
        stmt = select(LiquidationModel.value_base_delivered).where(LiquidationModel.route_id == route.id, LiquidationModel.active.is_(True))
        stmt = stmt.where(LiquidationModel.collector_id == collector_id) if collector_id else stmt
        stmt = stmt.order_by(LiquidationModel.date.desc(), LiquidationModel.created_at.desc()).limit(1)
        last = (await self.db.execute(stmt)).scalar_one_or_none()
        if last is not None:
            return float(last), "last_closure"
        return max(float(route.initial_value or 0) - float(route.initial_expense or 0), 0.0), "route_initial"

    async def list_page(self, *, brand_id: Optional[UUID], route_ids: Optional[list], collector_id: Optional[UUID], route_id: Optional[UUID],
                        date_from: Optional[date], date_to: Optional[date], status: Optional[str], include_reopened: bool,
                        params: PaginationParams, currency: Optional[str] = None) -> tuple[list[dict], int, dict]:
        stmt = _read_select()
        if currency:
            stmt = stmt.where(RouteModel.currency == currency)
        if brand_id is not None:
            stmt = stmt.where(RouteModel.brand_id == brand_id)
        if route_ids is not None:
            stmt = stmt.where(LiquidationModel.route_id.in_(route_ids))
        if route_id:
            stmt = stmt.where(LiquidationModel.route_id == route_id)
        if collector_id:
            stmt = stmt.where(LiquidationModel.collector_id == collector_id)
        if date_from:
            stmt = stmt.where(LiquidationModel.date >= date_from)
        if date_to:
            stmt = stmt.where(LiquidationModel.date <= date_to)
        if status == "pendiente":
            stmt = stmt.where(LiquidationModel.admin_confirmed_at.is_(None), LiquidationModel.reopened_at.is_(None), LiquidationModel.active.is_(True))
        elif status == "confirmada":
            stmt = stmt.where(LiquidationModel.admin_confirmed_at.isnot(None), LiquidationModel.reopened_at.is_(None))
        elif status == "reabierta":
            stmt = stmt.where(LiquidationModel.reopened_at.isnot(None))
        elif not include_reopened:
            stmt = stmt.where(LiquidationModel.active.is_(True))
        order = (LiquidationModel.created_at.asc(),) if status == "pendiente" else (LiquidationModel.date.desc(), LiquidationModel.created_at.desc())
        totals = await self._totals(stmt)
        rows, total = await paginate_mappings(self.db, stmt.order_by(*order), params)
        items = [_to_read(r) for r in rows]
        for item in items:
            await self._flag_outdated(item)
        return items, total, totals

    async def _totals(self, filtered) -> dict:
        """Totales de TODO el filtro (no solo de la página) para la fila "Totales período filtrado"."""
        sub = filtered.order_by(None).subquery()
        row = (await self.db.execute(select(
            func.count().label("count"),
            func.coalesce(func.sum(sub.c.total_value_charged), 0).label("collected"),
            func.coalesce(func.sum(sub.c.total_value_expenses), 0).label("expenses"),
            func.coalesce(func.sum(sub.c.value_new_loans), 0).label("new_loans"),
            func.coalesce(func.sum(sub.c.new_loans_count), 0).label("new_loans_count"),
            func.coalesce(func.sum(sub.c.expected_cash), 0).label("expected"),
            func.coalesce(func.sum(sub.c.cash_delivered), 0).label("delivered"),
            func.coalesce(func.sum(sub.c.difference), 0).label("difference"),
        ).select_from(sub))).mappings().one()
        return {k: (int(v) if k in ("count", "new_loans_count") else float(v)) for k, v in row.items()}

    async def _flag_outdated(self, item: dict) -> None:
        """Marca un cierre pendiente como desactualizado y cuantifica lo cobrado después del envío."""
        item.update(outdated=False, outdated_amount=0.0, late_receipts=0)
        if item["status"] != "pendiente" or not item["active"]:
            return
        current = await calc.compute_figures(self.db, item["route_id"], item["date"], item["collector_id"], item["id"])
        gap = current["collected_total"] - item["total_value_charged"]
        item["outdated"] = (abs(gap) > calc.TOLERANCE or abs(current["expenses_total"] - item["total_value_expenses"]) > calc.TOLERANCE
                            or abs(current["new_loans_total"] - item["value_new_loans"]) > calc.TOLERANCE)
        item["outdated_amount"] = round(max(gap, 0), 2)
        item["late_receipts"] = max(current["receipts_count"] - item["receipts_count"], 0)

    # ---- cierre ----
    async def create(self, *, route_id: UUID, day: date, collector_id: Optional[UUID], base: float, cash: float, note: Optional[str], closed_by: UUID) -> dict:
        try:
            figures = await calc.compute_figures(self.db, route_id, day, collector_id)
            expected = calc.expected_cash(base, figures)
            liquidation = LiquidationModel(
                date=day, route_id=route_id, collector_id=collector_id,
                today_collection_goal=figures["goal"], value_base_delivered=base,
                total_value_charged=figures["collected_total"], total_value_expenses=figures["expenses_total"],
                value_new_loans=figures["new_loans_total"], receipts_count=figures["receipts_count"], new_loans_count=figures["new_loans_count"],
                beak_generated=figures["beak_generated"], cash_delivered=cash, expected_cash=expected,
                difference=round(cash - expected, 2), note=note,
            )
            self.db.add(liquidation)
            await self.db.flush()

            today = today_bogota()
            # Dos UPDATE en lote (uno por tabla), no pago por pago: marca liquidado, fecha, cierre y responsable.
            mark = dict(liquidated=True, date_liquidated=today, liquidation_id=liquidation.id, liquidated_by=closed_by)
            await self.db.execute(update(PaymentModel).where(PaymentModel.id.in_(calc.linked_payment_ids(route_id, day, collector_id))).values(**mark))
            await self.db.execute(update(ExpenseModel).where(ExpenseModel.id.in_(calc.linked_expense_ids(route_id, day, collector_id))).values(**mark))
            await self.db.commit()
            return await self.get_read(liquidation.id)
        except IntegrityError as e:
            await self.db.rollback()
            raise ConflictException("Ya existe una liquidación para esta ruta, cobrador y fecha" if "uq_liquidations" in str(e) else ValidatorErrors.integrity_error(e))
        except Exception:
            await self.db.rollback()
            raise

    async def confirm(self, liquidation_id: UUID, confirmed_by: UUID) -> dict:
        model = await self.get_model(liquidation_id)
        if not model.active or model.reopened_at is not None:
            raise ConflictException("La liquidación fue reabierta o eliminada")
        if model.admin_confirmed_at:
            raise ConflictException("La liquidación ya fue confirmada")
        if await self.is_outdated(model):
            raise ConflictException("La liquidación está desactualizada (hay cobros o gastos nuevos): reábrela y vuelve a cerrar")
        model.admin_confirmed_at = datetime.now(timezone.utc)
        model.admin_confirmed_by = confirmed_by
        await self.db.commit()
        return await self.get_read(liquidation_id)

    async def _release(self, liquidation_id: UUID) -> None:
        """Devuelve pagos y gastos del cierre al estado "sin liquidar"."""
        clear = dict(liquidated=False, date_liquidated=None, liquidation_id=None, liquidated_by=None)
        await self.db.execute(update(PaymentModel).where(PaymentModel.liquidation_id == liquidation_id).values(**clear))
        await self.db.execute(update(ExpenseModel).where(ExpenseModel.liquidation_id == liquidation_id).values(**clear))

    async def reopen(self, liquidation_id: UUID, reopened_by: UUID) -> dict:
        model = await self.get_model(liquidation_id)
        if not model.active:
            raise ConflictException("La liquidación ya está cerrada o eliminada")
        await self._release(liquidation_id)
        model.active = False
        model.reopened_at = datetime.now(timezone.utc)
        model.reopened_by = reopened_by
        await self.db.commit()
        return await self.get_read(liquidation_id)

    async def delete_unconfirmed(self, liquidation_id: UUID) -> None:
        model = await self.get_model(liquidation_id)
        if model.admin_confirmed_at:
            raise ConflictException("La liquidación está confirmada: un admin debe reabrirla")
        await self._release(liquidation_id)
        model.active = False
        await self.db.commit()

    async def update_note(self, liquidation_id: UUID, note: Optional[str]) -> dict:
        model = await self.get_model(liquidation_id)
        if model.admin_confirmed_at or not model.active:
            raise ConflictException("Solo se puede editar la nota de un cierre pendiente")
        model.note = note
        await self.db.commit()
        return await self.get_read(liquidation_id)

    async def is_outdated(self, model: LiquidationModel) -> bool:
        current = await calc.compute_figures(self.db, model.route_id, model.date, model.collector_id, model.id)
        return (abs(current["collected_total"] - float(model.total_value_charged or 0)) > calc.TOLERANCE
                or abs(current["expenses_total"] - float(model.total_value_expenses or 0)) > calc.TOLERANCE
                or abs(current["new_loans_total"] - float(model.value_new_loans or 0)) > calc.TOLERANCE)

    async def detail(self, liquidation_id: UUID, hide_creator_for: Optional[UUID] = None) -> dict:
        data = await self.get_read(liquidation_id)
        day, route_id, collector_id = data["date"], data["route_id"], data["collector_id"]
        if data["active"]:
            current = await calc.compute_figures(self.db, route_id, day, collector_id, liquidation_id)
        else:  # cierre reabierto: no tiene pagos enlazados, se muestra lo guardado
            current = {"collected_total": data["total_value_charged"], "expenses_total": data["total_value_expenses"], "new_loans_total": data["value_new_loans"]}
        outdated = data["active"] and (
            abs(current["collected_total"] - data["total_value_charged"]) > calc.TOLERANCE
            or abs(current["expenses_total"] - data["total_value_expenses"]) > calc.TOLERANCE
            or abs(current["new_loans_total"] - data["value_new_loans"]) > calc.TOLERANCE)
        data.update(
            outdated=bool(outdated),
            current_total_charged=current["collected_total"], current_total_expenses=current["expenses_total"], current_new_loans=current["new_loans_total"],
            payments=await calc.payment_lines(self.db, route_id, day, collector_id, liquidation_id) if data["active"] else [],
            expenses=await calc.expense_lines(self.db, route_id, day, collector_id, liquidation_id, hide_creator_for) if data["active"] else [],
            new_loans=await calc.new_loan_lines(self.db, route_id, day, collector_id, hide_creator_for),
        )
        return data

    async def available_cash(self, route_id: UUID, day: date) -> dict:
        """Efectivo con el que cuenta la ruta ese día para entregar créditos nuevos: base + cuotas cobradas (sin los excedentes
        de los abonos extra) − gastos − créditos ya entregados. Es de toda la ruta, no de un cobrador."""
        route = await self.get_route(route_id)
        figures = await calc.compute_figures(self.db, route_id, day, None)
        base, base_source = await self.suggested_base(route, None)
        collected = figures["collected_total"] - figures["beak_generated"]
        available = round(base + collected - figures["expenses_total"] - figures["new_loans_total"], 2)
        return {
            "route_id": route_id, "date": day, "base": base, "base_source": base_source, "collected": round(collected, 2),
            "expenses": figures["expenses_total"], "new_loans": figures["new_loans_total"], "available": max(available, 0.0),
        }

    async def preview(self, route_id: UUID, day: date, collector_id: Optional[UUID], hide_creator_for: Optional[UUID] = None) -> dict:
        route = await self.get_route(route_id)
        figures = await calc.compute_figures(self.db, route_id, day, collector_id)
        base, base_source = await self.suggested_base(route, collector_id)
        existing = await self.active_for(route_id, day, collector_id)
        goal_paid = figures["collected_due_today"]
        return {
            **figures,
            "route_id": route_id, "route_name": route.name, "collector_id": collector_id,
            "collector_name": await self.user_name(collector_id), "date": day, "suggested_base": base, "suggested_base_source": base_source,
            "expected_cash": calc.expected_cash(base, figures),
            "progress_percent": round(min(100.0, goal_paid / figures["goal"] * 100), 1) if figures["goal"] else 0.0,
            "expenses": await calc.expense_lines(self.db, route_id, day, collector_id, hide_creator_for=hide_creator_for),
            "new_loans": await calc.new_loan_lines(self.db, route_id, day, collector_id, hide_creator_for),
            "existing_liquidation_id": existing["id"] if existing else None,
            "existing_status": existing["status"] if existing else None,
        }

    @staticmethod
    def ensure_closable(day: date) -> None:
        if day > today_bogota():
            raise BadRequestException("No se puede cerrar la caja de una fecha futura")
