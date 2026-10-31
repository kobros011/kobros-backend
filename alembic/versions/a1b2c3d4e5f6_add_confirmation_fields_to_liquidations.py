"""add_confirmation_fields_to_liquidations

Revision ID: a1b2c3d4e5f6
Revises: 8721fdd594fe
Create Date: 2026-10-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8721fdd594fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('liquidations', sa.Column('collector_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('liquidations', sa.Column('admin_confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('liquidations', sa.Column('admin_confirmed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True))


def downgrade() -> None:
    op.drop_column('liquidations', 'admin_confirmed_by')
    op.drop_column('liquidations', 'admin_confirmed_at')
    op.drop_column('liquidations', 'collector_id')
