"""add_guarantor_fields_and_client_references

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add guarantor columns to clients
    op.add_column('clients', sa.Column('guarantor_name', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('guarantor_cedula', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('guarantor_phone', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('guarantor_address', sa.String(), nullable=True))

    # Create client_references table
    op.create_table(
        'client_references',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
    )
    op.create_index('ix_client_references_client_id', 'client_references', ['client_id'])


def downgrade() -> None:
    op.drop_index('ix_client_references_client_id', table_name='client_references')
    op.drop_table('client_references')
    op.drop_column('clients', 'guarantor_address')
    op.drop_column('clients', 'guarantor_phone')
    op.drop_column('clients', 'guarantor_cedula')
    op.drop_column('clients', 'guarantor_name')
