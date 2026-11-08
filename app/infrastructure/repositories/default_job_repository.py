"""Pasa a `mora` las cuotas vencidas sin cobrar y suma su faltante a `loans.total_default` (una sola sentencia)."""
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.Emun import PaymentStatus
from .loan_stats import UNPAID_TOLERANCE

_SQL = text(f"""
WITH flipped AS (
    UPDATE payments p
       SET status = :mora
      FROM loans l
      JOIN clientsroutes cr ON cr.id = l.clientroute_id
      JOIN routes r ON r.id = cr.route_id
     WHERE p.loan_id = l.id
       AND p.status = :pending
       AND p.active IS NOT FALSE
       AND l.active IS NOT FALSE
       AND r.active IS NOT FALSE
       AND p.pay_date < :today
       AND coalesce(p.applied, 0) < p.value - {UNPAID_TOLERANCE}
    RETURNING p.loan_id, p.value - coalesce(p.applied, 0) AS shortfall
), per_loan AS (
    SELECT loan_id, sum(shortfall) AS shortfall FROM flipped GROUP BY loan_id
), bumped AS (
    UPDATE loans l
       SET total_default = coalesce(l.total_default, 0) + pl.shortfall
      FROM per_loan pl
     WHERE l.id = pl.loan_id
    RETURNING l.id
)
SELECT (SELECT count(*) FROM flipped) AS payments, (SELECT count(*) FROM bumped) AS loans
""")


async def mark_overdue_payments(db: AsyncSession, today: date) -> tuple[int, int]:
    """Devuelve (cuotas marcadas, créditos afectados). No hace commit."""
    row = (await db.execute(_SQL, {"mora": PaymentStatus.default.value, "pending": PaymentStatus.pending.value, "today": today})).one()
    return int(row.payments), int(row.loans)
