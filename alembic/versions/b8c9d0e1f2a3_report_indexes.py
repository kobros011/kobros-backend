"""report_indexes

Índices para las consultas de Reportes (cartera, mora, cobro diario, períodos).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-11-07

"""
from alembic import op

revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None

INDEXES = [
    ('ix_payments_loan_id', 'payments', ['loan_id']),
    ('ix_payments_pay_date', 'payments', ['pay_date']),
    ('ix_payments_payment_date', 'payments', ['payment_date']),
    ('ix_expenses_route_id_date', 'expenses', ['route_id', 'date']),
    ('ix_clientsroutes_route_id', 'clientsroutes', ['route_id']),
    ('ix_clientsroutes_cliente_id', 'clientsroutes', ['cliente_id']),
    ('ix_loans_clientroute_id', 'loans', ['clientroute_id']),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns, if_not_exists=True)


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
