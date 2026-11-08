"""payment_collected_by

Guarda qué usuario registró cada abono (columna nueva; los pagos antiguos quedan en NULL).

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-11-07

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('payments', sa.Column('collected_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_payments_collected_by_users', 'payments', 'users', ['collected_by'], ['id'])
    op.create_index('ix_payments_collected_by', 'payments', ['collected_by'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_payments_collected_by', table_name='payments')
    op.drop_constraint('fk_payments_collected_by_users', 'payments', type_='foreignkey')
    op.drop_column('payments', 'collected_by')
