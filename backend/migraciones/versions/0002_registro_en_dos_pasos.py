"""Registro del requerimiento en dos pasos (cambio 15 de la Tabla 26 de la Práctica 7).

El paso 1 registra los datos presupuestales y obtiene el semáforo; solo con semáforo vigente
verde se habilita el paso 2, donde el Área Usuaria registra la especificación técnica de cada
ítem, el plazo y el lugar de entrega, y envía el requerimiento a la Gerencia de Administración.
No agrega tablas ni estados: cuatro columnas y una regla de integridad (RI-28).

La transición nueva de Cuadro comparativo registrado a Anulado (cambio 16) es un dato de
catálogo y la agregan los scripts de semilla.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE requerimiento_item
            ADD COLUMN especificacion VARCHAR(1000);

        ALTER TABLE requerimiento
            ADD COLUMN plazo_entrega_dias SMALLINT CHECK (plazo_entrega_dias > 0),
            ADD COLUMN lugar_entrega      VARCHAR(250),
            ADD COLUMN fecha_envio        TIMESTAMPTZ,
            -- RI-28: no se envía a la Gerencia sin el plazo y el lugar de entrega del paso 2.
            ADD CONSTRAINT ri28_envio_con_paso_2 CHECK (
                fecha_envio IS NULL
                OR (plazo_entrega_dias IS NOT NULL AND lugar_entrega IS NOT NULL)
            ),
            ADD CONSTRAINT ri28_envio_posterior_al_registro CHECK (
                fecha_envio IS NULL OR fecha_envio >= fecha_registro
            );
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE requerimiento
            DROP CONSTRAINT ri28_envio_posterior_al_registro,
            DROP CONSTRAINT ri28_envio_con_paso_2,
            DROP COLUMN fecha_envio,
            DROP COLUMN lugar_entrega,
            DROP COLUMN plazo_entrega_dias;

        ALTER TABLE requerimiento_item
            DROP COLUMN especificacion;
    """)
