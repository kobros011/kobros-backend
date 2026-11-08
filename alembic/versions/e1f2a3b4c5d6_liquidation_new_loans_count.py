"""liquidation_new_loans_count

Guarda cuántos créditos nuevos incluyó cada cierre (columna "Créditos nuevos (n)" del historial).

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-11-07

"""
import sqlalchemy as sa
from alembic import op

revision = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('liquidations', sa.Column('new_loans_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('liquidations', 'new_loans_count')
