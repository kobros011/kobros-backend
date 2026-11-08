"""currencies

Monedas por marca (`brand_settings.currencies`, la primera es la principal) y por ruta (`routes.currency`).

Los datos que ya existen venían en pesos colombianos: se rellenan con COP **solo en esta migración**; la
aplicación no tiene una moneda por defecto (una marca nueva debe configurar sus monedas).

Revision ID: a4b5c6d7e8f9
Revises: a3b4c5d6e7f8
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = 'a4b5c6d7e8f9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('brand_settings', sa.Column('currencies', sa.JSON(), nullable=False, server_default='[]'))
    op.execute("UPDATE brand_settings SET currencies = '[\"COP\"]'")
    # Marcas sin fila de configuración: se crea con la moneda histórica para que sus rutas existentes tengan a qué apuntar.
    op.execute("""
        INSERT INTO brand_settings (id, brand_id, currencies, number_format_style, number_decimals, active, created_at)
        SELECT gen_random_uuid(), b.id, '["COP"]', 'comma-thousands', 2, true, now()
        FROM brands b
        WHERE NOT EXISTS (SELECT 1 FROM brand_settings s WHERE s.brand_id = b.id)
    """)

    op.add_column('routes', sa.Column('currency', sa.String(length=3), nullable=True))
    op.execute("UPDATE routes SET currency = 'COP'")
    op.alter_column('routes', 'currency', nullable=False)


def downgrade() -> None:
    op.drop_column('routes', 'currency')
    op.drop_column('brand_settings', 'currencies')
