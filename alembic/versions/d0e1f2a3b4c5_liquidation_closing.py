"""liquidation_closing

Cierre de caja con cuadre: la liquidación guarda lo calculado por el servidor (efectivo esperado, entregado y
diferencia), los pagos/gastos quedan enlazados al cierre (`liquidation_id`) para poder reabrirlo, y se registra quién
creó cada crédito y cada gasto para atribuirlos al cobrador. Un cierre activo por (ruta, cobrador, día).

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-11-07

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # liquidations: cuadre y reapertura
    op.add_column('liquidations', sa.Column('cash_delivered', sa.Float(), nullable=True))
    op.add_column('liquidations', sa.Column('expected_cash', sa.Float(), nullable=True))
    op.add_column('liquidations', sa.Column('difference', sa.Float(), nullable=True))
    op.add_column('liquidations', sa.Column('receipts_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('liquidations', sa.Column('beak_generated', sa.Float(), nullable=False, server_default='0'))
    op.add_column('liquidations', sa.Column('note', sa.Text(), nullable=True))
    op.add_column('liquidations', sa.Column('reopened_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('liquidations', sa.Column('reopened_by', UUID, sa.ForeignKey('users.id'), nullable=True))

    # enlace de pagos y gastos con el cierre que los incluyó
    op.add_column('payments', sa.Column('liquidation_id', UUID, sa.ForeignKey('liquidations.id'), nullable=True))
    op.add_column('expenses', sa.Column('liquidation_id', UUID, sa.ForeignKey('liquidations.id'), nullable=True))
    op.create_index('ix_payments_liquidation_id', 'payments', ['liquidation_id'])
    op.create_index('ix_expenses_liquidation_id', 'expenses', ['liquidation_id'])

    # quién creó el crédito / el gasto (atribución al cobrador)
    op.add_column('loans', sa.Column('created_by', UUID, sa.ForeignKey('users.id'), nullable=True))
    op.add_column('expenses', sa.Column('created_by', UUID, sa.ForeignKey('users.id'), nullable=True))
    op.create_index('ix_loans_created_by', 'loans', ['created_by'])
    op.create_index('ix_expenses_created_by', 'expenses', ['created_by'])

    # liquidated nunca debe ser NULL (un gasto con NULL jamás se liquidaba)
    op.execute("UPDATE expenses SET liquidated = false WHERE liquidated IS NULL")
    op.execute("UPDATE payments SET liquidated = false WHERE liquidated IS NULL")
    op.alter_column('expenses', 'liquidated', server_default=sa.text('false'))
    op.alter_column('payments', 'liquidated', server_default=sa.text('false'))

    # un cierre activo por ruta, cobrador (NULL = consolidado) y día; bloquea el doble cierre concurrente
    op.execute(
        "CREATE UNIQUE INDEX uq_liquidations_route_collector_date ON liquidations "
        "(route_id, date, COALESCE(collector_id, '00000000-0000-0000-0000-000000000000'::uuid)) WHERE active"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_liquidations_route_collector_date")
    op.drop_index('ix_expenses_created_by', table_name='expenses')
    op.drop_index('ix_loans_created_by', table_name='loans')
    op.drop_column('expenses', 'created_by')
    op.drop_column('loans', 'created_by')
    op.drop_index('ix_expenses_liquidation_id', table_name='expenses')
    op.drop_index('ix_payments_liquidation_id', table_name='payments')
    op.drop_column('expenses', 'liquidation_id')
    op.drop_column('payments', 'liquidation_id')
    for column in ('reopened_by', 'reopened_at', 'note', 'beak_generated', 'receipts_count', 'difference', 'expected_cash', 'cash_delivered'):
        op.drop_column('liquidations', column)
