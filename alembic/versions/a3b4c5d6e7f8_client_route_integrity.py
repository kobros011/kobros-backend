"""client_route_integrity

Un cliente solo puede estar una vez (activo) en cada ruta y las prioridades de una ruta quedan 1..n.

Antes de crear el índice único:
  * los (cliente, ruta) activos repetidos se fusionan en el más antiguo (sus créditos se reasignan a él);
  * las prioridades de cada ruta se renumeran 1..n según su orden actual.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-11-08

"""
from alembic import op

revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) duplicados activos: los créditos pasan a la fila que se conserva y las demás se desactivan
    op.execute("""
        WITH ranked AS (
            SELECT id,
                   first_value(id) OVER w AS keep_id,
                   row_number() OVER w AS rn
            FROM clientsroutes
            WHERE active IS NOT FALSE
            WINDOW w AS (PARTITION BY cliente_id, route_id ORDER BY created_at, id)
        ), moved AS (
            UPDATE loans l SET clientroute_id = r.keep_id
            FROM ranked r
            WHERE l.clientroute_id = r.id AND r.rn > 1
            RETURNING l.id
        )
        UPDATE clientsroutes cr SET active = false
        FROM ranked r
        WHERE cr.id = r.id AND r.rn > 1
    """)

    # 2) prioridades 1..n por ruta (sin repetidos ni huecos)
    op.execute("""
        UPDATE clientsroutes cr SET "order" = t.rn
        FROM (
            SELECT id, row_number() OVER (PARTITION BY route_id ORDER BY "order", created_at, id) AS rn
            FROM clientsroutes
            WHERE active IS NOT FALSE
        ) t
        WHERE cr.id = t.id AND cr."order" <> t.rn
    """)

    # 3) un cliente, una vez por ruta
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_clientsroutes_client_route_active
        ON clientsroutes (cliente_id, route_id)
        WHERE active IS NOT FALSE
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_clientsroutes_client_route_active")
