"""liquidated_by

Quién liquidó cada pago y cada gasto (junto con `date_liquidated` y `liquidation_id` ya existentes).

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-11-08

"""
from alembic import op
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa

revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    for table in ('payments', 'expenses'):
        op.add_column(table, sa.Column('liquidated_by', UUID, sa.ForeignKey('users.id'), nullable=True))
        op.create_index(f'ix_{table}_liquidated_by', table, ['liquidated_by'])
    # Lo ya liquidado antes de esta columna queda atribuido a quien confirmó o, si no, al cobrador del cierre.
    for table in ('payments', 'expenses'):
        op.execute(f"""
            UPDATE {table} t SET liquidated_by = COALESCE(l.admin_confirmed_by, l.collector_id)
            FROM liquidations l WHERE t.liquidation_id = l.id AND t.liquidated_by IS NULL
        """)


def downgrade() -> None:
    for table in ('expenses', 'payments'):
        op.drop_index(f'ix_{table}_liquidated_by', table_name=table)
        op.drop_column(table, 'liquidated_by')
