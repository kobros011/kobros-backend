"""add_logo_dimensions

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-07

"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('brand_settings', sa.Column('logo_width', sa.Integer(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_height', sa.Integer(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_tone', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('brand_settings', 'logo_tone')
    op.drop_column('brand_settings', 'logo_height')
    op.drop_column('brand_settings', 'logo_width')
