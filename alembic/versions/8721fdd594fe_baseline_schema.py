"""baseline_schema

Revision ID: 8721fdd594fe
Revises:
Create Date: 2026-10-30 20:37:57.239604

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8721fdd594fe'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # brands
    op.create_table(
        'brands',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('routes_available', sa.Integer(), default=0, nullable=False),
    )

    # users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('username', sa.String(), unique=True, nullable=False),
        sa.Column('hashed_password', sa.Text(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('type_user', sa.Enum('dev', 'super', 'admin', 'partner', 'collector', name='usertype'), nullable=False),
        sa.Column('document_id', sa.String(), nullable=True),
        sa.Column('linking_date', sa.Date(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('mobile', sa.String(), nullable=True),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('department', sa.String(), nullable=True),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.id'), nullable=True),
        sa.Column('clerk_user_id', sa.String(64), unique=True, nullable=True),
    )

    # routes
    op.create_table(
        'routes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('initial_value', sa.Float(), nullable=False),
        sa.Column('initial_expense', sa.Float(), nullable=False),
        sa.Column('opening_date', sa.Date(), nullable=False),
        sa.Column('loans_number', sa.Integer(), default=0, nullable=False),
        sa.Column('allowed_users_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.id'), nullable=False),
    )

    # clients
    op.create_table(
        'clients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('id_document', sa.String(), nullable=False),
        sa.Column('current_address', sa.Text(), nullable=True),
        sa.Column('neighborhood', sa.String(), nullable=True),
        sa.Column('current_phone', sa.String(), nullable=True),
        sa.Column('current_mobile', sa.String(), nullable=True),
        sa.Column('linking_date', sa.Date(), nullable=True),
        sa.Column('beak', sa.Float(), default=0, nullable=True),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.id'), nullable=True),
    )

    # clientsroutes
    op.create_table(
        'clientsroutes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('cliente_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id'), nullable=True),
        sa.Column('route_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('routes.id'), nullable=True),
    )

    # loans
    op.create_table(
        'loans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('loan_number', sa.Integer(), nullable=False),
        sa.Column('initial_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('value_quota_fixed', sa.Float(), nullable=True),
        sa.Column('pending_quotas', sa.Integer(), default=0),
        sa.Column('canceled_quotas', sa.Integer(), default=0),
        sa.Column('agreed_quotas', sa.Integer(), nullable=False),
        sa.Column('total_default', sa.Float(), default=0),
        sa.Column('date_first_quota', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(), nullable=False),
        sa.Column('fixed_payment_day', sa.SmallInteger(), nullable=True),
        sa.Column('value_capital', sa.Float(), nullable=True),
        sa.Column('value_utility_loan', sa.Float(), nullable=True),
        sa.Column('value_total_loan', sa.Float(), nullable=True),
        sa.Column('interest_rate', sa.Float(), nullable=True),
        sa.Column('clientroute_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clientsroutes.id'), nullable=True),
    )

    # payments
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pay_date', sa.Date(), nullable=True),
        sa.Column('payment_date', sa.Date(), nullable=True),
        sa.Column('quota_number', sa.Integer(), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('credit_value', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('applied', sa.Float(), nullable=True),
        sa.Column('liquidated', sa.Boolean(), default=False),
        sa.Column('date_liquidated', sa.Date(), nullable=True),
        sa.Column('loan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('loans.id'), nullable=True),
    )

    # expensesconcept
    op.create_table(
        'expensesconcept',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('concept', sa.String(), nullable=True),
        sa.Column('keyIcon', sa.String(), nullable=True),
        sa.Column('color', sa.String(), nullable=True),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.id'), nullable=False),
    )

    # expenses
    op.create_table(
        'expenses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('user_generated', sa.String(), nullable=False),
        sa.Column('liquidated', sa.Boolean(), nullable=True),
        sa.Column('date_liquidated', sa.Date(), nullable=True),
        sa.Column('expensesconcept_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('expensesconcept.id'), nullable=True),
        sa.Column('route_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('routes.id'), nullable=True),
    )

    # liquidations (sin los campos de confirmación — esos los agrega a1b2c3d4e5f6)
    op.create_table(
        'liquidations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('today_collection_goal', sa.Float(), nullable=True),
        sa.Column('value_base_delivered', sa.Float(), nullable=True),
        sa.Column('total_value_charged', sa.Float(), nullable=True),
        sa.Column('total_value_expenses', sa.Float(), nullable=True),
        sa.Column('value_new_loans', sa.Float(), nullable=True),
        sa.Column('route_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('routes.id'), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('liquidations')
    op.drop_table('expenses')
    op.drop_table('expensesconcept')
    op.drop_table('payments')
    op.drop_table('loans')
    op.drop_table('clientsroutes')
    op.drop_table('clients')
    op.drop_table('routes')
    op.drop_table('users')
    op.drop_table('brands')
    op.execute('DROP TYPE IF EXISTS usertype')
