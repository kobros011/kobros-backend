"""client_contacts

Fiadores y referencias pasan a una tabla de contactos del cliente (`client_contacts`): tipo, nombre, celular
(obligatorios) y dirección, con `position` por tipo (1 = principal) y sin tope de cantidad.

Datos existentes: el fiador de `clients.guarantor_*` y cada fila de `client_references` se copian como contactos y
después se eliminan esas columnas y esa tabla. La cédula del fiador se descarta (ya no se captura). Si el fiador
no tenía celular se guarda `''` para cumplir el NOT NULL; la migración avisa cuántos quedaron así.

Revision ID: a5b6c7d8e9f0
Revises: a4b5c6d7e8f9
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'a5b6c7d8e9f0'
down_revision = 'a4b5c6d7e8f9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'client_contacts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.CheckConstraint("kind IN ('fiador', 'referencia')", name='ck_client_contacts_kind'),
    )
    op.create_index('ix_client_contacts_client_id', 'client_contacts', ['client_id'])

    op.execute("""
        INSERT INTO client_contacts (id, client_id, kind, name, phone, address, position, created_at)
        SELECT gen_random_uuid(), c.id, 'fiador', COALESCE(NULLIF(btrim(c.guarantor_name), ''), 'Fiador'),
               COALESCE(NULLIF(btrim(c.guarantor_phone), ''), ''), NULLIF(btrim(c.guarantor_address), ''), 1, now()
        FROM clients c
        WHERE NULLIF(btrim(c.guarantor_name), '') IS NOT NULL OR NULLIF(btrim(c.guarantor_phone), '') IS NOT NULL
    """)
    op.execute("""
        INSERT INTO client_contacts (id, client_id, kind, name, phone, address, position, active, created_at)
        SELECT gen_random_uuid(), r.client_id, 'referencia', r.name, COALESCE(NULLIF(btrim(r.phone), ''), ''),
               NULLIF(btrim(r.address), ''),
               row_number() OVER (PARTITION BY r.client_id ORDER BY r.created_at, r.id), r.active, now()
        FROM client_references r
    """)
    missing = op.get_bind().execute(sa.text("SELECT count(*) FROM client_contacts WHERE phone = ''")).scalar()
    if missing:
        print(f"[client_contacts] {missing} contacto(s) migrados sin celular: complétalos desde el cliente.")

    op.drop_index('ix_client_references_client_id', table_name='client_references')
    op.drop_table('client_references')
    for column in ('guarantor_name', 'guarantor_cedula', 'guarantor_phone', 'guarantor_address'):
        op.drop_column('clients', column)


def downgrade() -> None:
    """Mejor esfuerzo: vuelve el fiador principal a `clients` y las referencias a `client_references`; se pierde lo que exceda 1 fiador."""
    for column in ('guarantor_name', 'guarantor_cedula', 'guarantor_phone', 'guarantor_address'):
        op.add_column('clients', sa.Column(column, sa.String(), nullable=True))
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
    op.execute("""
        UPDATE clients c SET guarantor_name = k.name, guarantor_phone = NULLIF(k.phone, ''), guarantor_address = k.address
        FROM client_contacts k WHERE k.client_id = c.id AND k.kind = 'fiador' AND k.position = 1
    """)
    op.execute("""
        INSERT INTO client_references (id, name, address, phone, client_id, active)
        SELECT gen_random_uuid(), name, address, NULLIF(phone, ''), client_id, active
        FROM client_contacts WHERE kind = 'referencia' ORDER BY client_id, position
    """)
    op.drop_index('ix_client_contacts_client_id', table_name='client_contacts')
    op.drop_table('client_contacts')
