"""split_logo_full_mark

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-07

"""
from alembic import op
import sqlalchemy as sa

revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('brand_settings', 'logo_blob')
    op.drop_column('brand_settings', 'logo_width')
    op.drop_column('brand_settings', 'logo_height')
    op.drop_column('brand_settings', 'logo_tone')

    op.add_column('brand_settings', sa.Column('logo_full_blob', sa.String(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_full_width', sa.Integer(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_full_height', sa.Integer(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_full_tone', sa.String(), nullable=True))

    op.add_column('brand_settings', sa.Column('logo_mark_blob', sa.String(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_mark_width', sa.Integer(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_mark_height', sa.Integer(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_mark_tone', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('brand_settings', 'logo_mark_tone')
    op.drop_column('brand_settings', 'logo_mark_height')
    op.drop_column('brand_settings', 'logo_mark_width')
    op.drop_column('brand_settings', 'logo_mark_blob')

    op.drop_column('brand_settings', 'logo_full_tone')
    op.drop_column('brand_settings', 'logo_full_height')
    op.drop_column('brand_settings', 'logo_full_width')
    op.drop_column('brand_settings', 'logo_full_blob')

    op.add_column('brand_settings', sa.Column('logo_tone', sa.String(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_height', sa.Integer(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_width', sa.Integer(), nullable=True))
    op.add_column('brand_settings', sa.Column('logo_blob', sa.String(), nullable=True))
