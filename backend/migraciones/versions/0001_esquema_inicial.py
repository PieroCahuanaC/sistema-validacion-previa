"""Esquema inicial: 23 tablas, 29 llaves foráneas, 15 índices y reglas de integridad.

Traduce el modelo lógico y el diccionario de datos de la Práctica 6 (Tablas 4 y 6 a 16).
Se aplica igual en el ambiente de desarrollo (PostgreSQL 17.6 en Docker) y en los proyectos
de Supabase de calidad y producción.

Revision ID: 0001
Revises:
Create Date: 2026-10-25
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLAS = [
    "rol", "unidad_organica", "usuario", "sesion", "bitacora",
    "carga_datos", "meta_presupuestal", "saldo_meta", "pac_item",
    "estado", "regla_semaforo", "requerimiento", "requerimiento_item",
    "validacion_presupuestal", "ajuste_requerimiento", "decision_presupuesto",
    "transicion", "historial_etapa", "tipo_documento", "revision_documento",
    "proveedor", "cuadro_comparativo", "cotizacion",
]

ACCIONES_BITACORA = (
    "'LOGIN_EXITOSO','LOGIN_FALLIDO','BLOQUEO_CUENTA','CIERRE_SESION','CAMBIO_CONTRASENA',"
    "'ACCESO_DENEGADO','REGISTRO_REQUERIMIENTO','VALIDACION_SEMAFORO','AJUSTE_REQUERIMIENTO',"
    "'DECISION_AMBAR','CAMBIO_ETAPA','REVISION_DOCUMENTO','REGISTRO_CUADRO','CONFIG_REGLA',"
    "'ALTA_USUARIO','MODIFICACION_USUARIO','BAJA_USUARIO','RESTABLECER_CONTRASENA',"
    "'EXTRACCION_DATOS','RESTAURACION_BD'"
)

DDL_TABLAS = f"""
-- 1.7.1 Usuarios, roles y sesiones -------------------------------------------------
CREATE TABLE rol (
    id_rol       SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo       VARCHAR(5)   NOT NULL UNIQUE CHECK (codigo IN ('AU','GA','JL','JP','ADM')),
    nombre       VARCHAR(60)  NOT NULL UNIQUE,
    descripcion  VARCHAR(200)
);

CREATE TABLE unidad_organica (
    id_unidad  SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre     VARCHAR(120) NOT NULL UNIQUE,
    sigla      VARCHAR(15),
    activa     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE usuario (
    id_usuario           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_rol               SMALLINT NOT NULL REFERENCES rol ON DELETE RESTRICT,           -- R1
    id_unidad            SMALLINT REFERENCES unidad_organica ON DELETE RESTRICT,        -- R2
    nombre_usuario       VARCHAR(30)  NOT NULL UNIQUE,
    nombres_apellidos    VARCHAR(120) NOT NULL,
    hash_contrasena      VARCHAR(255) NOT NULL,
    contrasena_temporal  BOOLEAN  NOT NULL DEFAULT TRUE,
    intentos_fallidos    SMALLINT NOT NULL DEFAULT 0 CHECK (intentos_fallidos >= 0),
    bloqueado_hasta      TIMESTAMPTZ,
    estado               VARCHAR(10) NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO','BAJA'))
);

CREATE TABLE sesion (
    id_sesion    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario   INTEGER NOT NULL REFERENCES usuario ON DELETE RESTRICT,                -- R3
    hash_token   CHAR(64) NOT NULL UNIQUE,
    emitida_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expira_en    TIMESTAMPTZ NOT NULL,
    revocada_en  TIMESTAMPTZ,
    CHECK (expira_en > emitida_en)
);

-- 1.7.6 Bitácora de auditoría --------------------------------------------------------
CREATE TABLE bitacora (
    id_bitacora     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha_hora      TIMESTAMPTZ NOT NULL DEFAULT now(),
    id_usuario      INTEGER  REFERENCES usuario ON DELETE RESTRICT,                     -- R4
    id_rol          SMALLINT REFERENCES rol ON DELETE RESTRICT,                         -- R5
    actor_servicio  VARCHAR(30),
    accion          VARCHAR(30) NOT NULL CHECK (accion IN ({ACCIONES_BITACORA})),
    recurso_tipo    VARCHAR(20) CHECK (recurso_tipo IN
                    ('REQUERIMIENTO','USUARIO','REGLA','CARGA','SESION','RESPALDO')),
    recurso_id      BIGINT,
    resultado       VARCHAR(10) NOT NULL CHECK (resultado IN ('EXITO','DENEGADO','ERROR')),
    detalle         JSONB,
    ip_origen       INET,
    id_traza        UUID NOT NULL,
    hash_anterior   CHAR(64),
    CHECK (id_usuario IS NOT NULL OR actor_servicio IS NOT NULL
           OR accion IN ('LOGIN_FALLIDO','BLOQUEO_CUENTA'))
);

-- 1.7.2 Base presupuestal y PAC ------------------------------------------------------
CREATE TABLE carga_datos (
    id_carga         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fuente           VARCHAR(10) NOT NULL CHECK (fuente IN ('MEF','SEACE')),
    origen           VARCHAR(12) NOT NULL CHECK (origen IN ('AUTOMATICA','MANUAL_CSV')),
    anio_fiscal      SMALLINT NOT NULL CHECK (anio_fiscal >= 2024),
    fecha_ejecucion  TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_corte      TIMESTAMPTZ,
    resultado        VARCHAR(10) NOT NULL CHECK (resultado IN ('EXITOSA','FALLIDA','RECHAZADA')),
    detalle_error    VARCHAR(500),
    CHECK (resultado <> 'EXITOSA' OR fecha_corte IS NOT NULL)                   -- RI-11
);

CREATE TABLE meta_presupuestal (
    id_meta      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    anio_fiscal  SMALLINT NOT NULL,
    codigo       VARCHAR(10) NOT NULL,
    nombre       VARCHAR(250) NOT NULL,
    activa       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (anio_fiscal, codigo)
);

CREATE TABLE saldo_meta (
    id_saldo          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_meta           INTEGER NOT NULL REFERENCES meta_presupuestal ON DELETE RESTRICT,  -- R8
    id_carga          INTEGER NOT NULL REFERENCES carga_datos ON DELETE RESTRICT,        -- R6
    pim               NUMERIC(14,2) NOT NULL CHECK (pim >= 0),
    certificacion     NUMERIC(14,2) NOT NULL CHECK (certificacion >= 0 AND certificacion <= pim),
    compromiso_anual  NUMERIC(14,2) NOT NULL
                      CHECK (compromiso_anual >= 0 AND compromiso_anual <= certificacion), -- RI-09
    UNIQUE (id_meta, id_carga)
);

CREATE TABLE pac_item (
    id_pac_item        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_carga           INTEGER NOT NULL REFERENCES carga_datos ON DELETE RESTRICT,       -- R7
    numero_referencia  VARCHAR(20)  NOT NULL,
    descripcion        VARCHAR(500) NOT NULL,
    tipo_objeto        VARCHAR(12)  NOT NULL
                       CHECK (tipo_objeto IN ('BIEN','SERVICIO','OBRA','CONSULTORIA')),
    valor_estimado     NUMERIC(14,2) NOT NULL CHECK (valor_estimado >= 0),
    UNIQUE (id_carga, numero_referencia)
);

-- 1.7.4 Catálogo de estados ----------------------------------------------------------
CREATE TABLE estado (
    id_estado    SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo       VARCHAR(30) NOT NULL UNIQUE,
    nombre       VARCHAR(60) NOT NULL,
    plazo_horas  SMALLINT CHECK (plazo_horas > 0),
    orden        SMALLINT NOT NULL UNIQUE,
    es_final     BOOLEAN NOT NULL DEFAULT FALSE
);

-- 1.7.5 Configuración de reglas ------------------------------------------------------
CREATE TABLE regla_semaforo (
    id_regla       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parametros     JSONB NOT NULL,
    vigente_desde  TIMESTAMPTZ NOT NULL DEFAULT now(),
    vigente_hasta  TIMESTAMPTZ,
    CHECK (vigente_hasta IS NULL OR vigente_hasta > vigente_desde)               -- RI-10
);

-- 1.7.3 Requerimientos y validación presupuestal --------------------------------------
CREATE SEQUENCE seq_codigo_requerimiento;

CREATE TABLE requerimiento (
    id_requerimiento     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo               VARCHAR(15) NOT NULL UNIQUE,
    id_unidad            SMALLINT NOT NULL REFERENCES unidad_organica ON DELETE RESTRICT,  -- R9
    id_meta              INTEGER  NOT NULL REFERENCES meta_presupuestal ON DELETE RESTRICT, -- R10
    id_pac_item          INTEGER  REFERENCES pac_item ON DELETE RESTRICT,                   -- R11
    id_estado_actual     SMALLINT NOT NULL REFERENCES estado ON DELETE RESTRICT,            -- R17
    objeto_contratacion  VARCHAR(10)  NOT NULL CHECK (objeto_contratacion IN ('BIEN','SERVICIO')),
    descripcion          VARCHAR(500) NOT NULL,
    monto_estimado       NUMERIC(14,2) NOT NULL CHECK (monto_estimado > 0),
    fecha_necesidad      DATE NOT NULL,
    fecha_registro       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (fecha_necesidad >= (fecha_registro AT TIME ZONE 'America/Lima')::date)  -- RI-10
);

CREATE TABLE requerimiento_item (
    id_item              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_requerimiento     INTEGER NOT NULL REFERENCES requerimiento ON DELETE RESTRICT,     -- R29
    descripcion          VARCHAR(250) NOT NULL,
    unidad_medida        VARCHAR(30)  NOT NULL,
    cantidad             NUMERIC(12,2) NOT NULL CHECK (cantidad > 0),
    precio_unitario_ref  NUMERIC(14,2) NOT NULL CHECK (precio_unitario_ref > 0),
    fuente_precio        VARCHAR(20) NOT NULL
                         CHECK (fuente_precio IN ('COTIZACION','COMPRA_ANTERIOR'))
);

CREATE TABLE validacion_presupuestal (
    id_validacion     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_requerimiento  INTEGER NOT NULL REFERENCES requerimiento ON DELETE RESTRICT,        -- R12
    id_saldo          INTEGER REFERENCES saldo_meta ON DELETE RESTRICT,                    -- R13
    id_regla          INTEGER NOT NULL REFERENCES regla_semaforo ON DELETE RESTRICT,       -- R14
    fecha_hora        TIMESTAMPTZ NOT NULL DEFAULT now(),
    monto_evaluado    NUMERIC(14,2) NOT NULL CHECK (monto_evaluado > 0),
    estado_semaforo   VARCHAR(5) NOT NULL CHECK (estado_semaforo IN ('VERDE','AMBAR','ROJO')),
    motivo            VARCHAR(30) NOT NULL CHECK (motivo IN ('DISPONIBLE',
                      'PRESUPUESTO_INSUFICIENTE','SIN_DATOS_META','DATO_DESACTUALIZADO',
                      'NO_PREVISTO_PAC')),
    CHECK (id_saldo IS NOT NULL OR motivo = 'SIN_DATOS_META')                    -- RI-11
);

CREATE TABLE ajuste_requerimiento (
    id_ajuste               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_validacion           INTEGER NOT NULL UNIQUE
                            REFERENCES validacion_presupuestal ON DELETE RESTRICT,      -- R15
    opcion                  VARCHAR(20) NOT NULL
                            CHECK (opcion IN ('REFORMULAR','REPROGRAMAR','NINGUNA')),
    monto_nuevo             NUMERIC(14,2) CHECK (monto_nuevo > 0),
    fecha_necesidad_nueva   DATE,
    fecha_hora              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (opcion <> 'REFORMULAR' OR monto_nuevo IS NOT NULL),                   -- RI-11
    CHECK (opcion <> 'REPROGRAMAR' OR fecha_necesidad_nueva IS NOT NULL)
);

CREATE TABLE decision_presupuesto (
    id_decision    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_validacion  INTEGER NOT NULL UNIQUE
                   REFERENCES validacion_presupuestal ON DELETE RESTRICT,               -- R16
    resultado      VARCHAR(12) NOT NULL CHECK (resultado IN ('CONFIRMADA','DENEGADA')),
    sustento       VARCHAR(500),
    fecha_hora     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (resultado <> 'DENEGADA' OR sustento IS NOT NULL)                      -- RI-11
);

-- 1.7.4 Expediente y trazabilidad -----------------------------------------------------
CREATE TABLE transicion (
    id_transicion      SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_estado_origen   SMALLINT NOT NULL REFERENCES estado ON DELETE RESTRICT,             -- R21
    id_estado_destino  SMALLINT NOT NULL REFERENCES estado ON DELETE RESTRICT,             -- R22
    id_rol             SMALLINT NOT NULL REFERENCES rol ON DELETE RESTRICT,                -- R23
    tipo               VARCHAR(10) NOT NULL CHECK (tipo IN ('AVANCE','DEVOLUCION','ANULACION')),
    UNIQUE (id_estado_origen, id_estado_destino),
    CHECK (id_estado_origen <> id_estado_destino)                                -- RI-12
);

CREATE TABLE historial_etapa (
    id_historial      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_requerimiento  INTEGER  NOT NULL REFERENCES requerimiento ON DELETE RESTRICT,       -- R18
    id_estado         SMALLINT NOT NULL REFERENCES estado ON DELETE RESTRICT,              -- R19
    id_rol            SMALLINT NOT NULL REFERENCES rol ON DELETE RESTRICT,                 -- R20
    fecha_hora        TIMESTAMPTZ NOT NULL DEFAULT now(),
    observacion       VARCHAR(500)
);

CREATE TABLE tipo_documento (
    id_tipo_documento  SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre             VARCHAR(100) NOT NULL UNIQUE,
    obligatorio        BOOLEAN NOT NULL DEFAULT TRUE,
    activo             BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE revision_documento (
    id_revision        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_requerimiento   INTEGER  NOT NULL REFERENCES requerimiento ON DELETE RESTRICT,      -- R24
    id_tipo_documento  SMALLINT NOT NULL REFERENCES tipo_documento ON DELETE RESTRICT,     -- R25
    resultado          VARCHAR(10) NOT NULL CHECK (resultado IN ('CONFORME','OBSERVADO')),
    observacion        VARCHAR(500),
    fecha_hora         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (resultado <> 'OBSERVADO' OR observacion IS NOT NULL)                  -- RI-11
);

CREATE TABLE proveedor (
    id_proveedor  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo_persona  VARCHAR(10)  NOT NULL CHECK (tipo_persona IN ('NATURAL','JURIDICA')),
    ruc           VARCHAR(255) NOT NULL,
    ruc_hash      CHAR(64)     NOT NULL UNIQUE,
    razon_social  VARCHAR(500) NOT NULL
);

CREATE TABLE cuadro_comparativo (
    id_cuadro          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_requerimiento   INTEGER NOT NULL UNIQUE
                       REFERENCES requerimiento ON DELETE RESTRICT,                      -- R26
    fecha_registro     TIMESTAMPTZ NOT NULL DEFAULT now(),
    precio_referencia  NUMERIC(14,2) NOT NULL CHECK (precio_referencia > 0),
    observacion        VARCHAR(500)
);

CREATE TABLE cotizacion (
    id_cotizacion     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_cuadro         INTEGER NOT NULL REFERENCES cuadro_comparativo ON DELETE RESTRICT,   -- R27
    id_proveedor      INTEGER NOT NULL REFERENCES proveedor ON DELETE RESTRICT,            -- R28
    monto             NUMERIC(14,2) NOT NULL CHECK (monto > 0),
    fecha_cotizacion  DATE NOT NULL,
    UNIQUE (id_cuadro, id_proveedor)
);
"""

# Tabla 22 de la Práctica 6: índices explícitos I-01 a I-15.
DDL_INDICES = """
CREATE INDEX i01_requerimiento_unidad_fecha ON requerimiento (id_unidad, fecha_necesidad);
CREATE INDEX i02_requerimiento_meta ON requerimiento (id_meta);
CREATE INDEX i03_requerimiento_estado ON requerimiento (id_estado_actual);
CREATE INDEX i04_historial_req_fecha ON historial_etapa (id_requerimiento, fecha_hora);
CREATE INDEX i05_validacion_req_fecha ON validacion_presupuestal
    (id_requerimiento, fecha_hora DESC);
CREATE INDEX i06_validacion_alertas ON validacion_presupuestal (fecha_hora)
    WHERE estado_semaforo IN ('AMBAR','ROJO');
CREATE INDEX i07_carga_ultima_exitosa ON carga_datos (fuente, fecha_corte DESC)
    WHERE resultado = 'EXITOSA';
CREATE INDEX i08_saldo_carga ON saldo_meta (id_carga);
CREATE INDEX i09_revision_req ON revision_documento (id_requerimiento);
CREATE INDEX i10_sesion_usuario ON sesion (id_usuario);
CREATE INDEX i11_bitacora_fecha ON bitacora USING BRIN (fecha_hora);
CREATE INDEX i12_bitacora_recurso ON bitacora (recurso_tipo, recurso_id);
CREATE INDEX i13_bitacora_usuario_fecha ON bitacora (id_usuario, fecha_hora);
CREATE UNIQUE INDEX i14_regla_vigente ON regla_semaforo ((vigente_hasta IS NULL))
    WHERE vigente_hasta IS NULL;
CREATE INDEX i15_item_requerimiento ON requerimiento_item (id_requerimiento);
"""

# Reglas de integridad reforzadas con disparadores (Tabla 16 de la Práctica 6).
DDL_DISPARADORES = """
-- RI-22: validaciones, ajustes, decisiones, historial y bitácora son de solo inserción.
CREATE FUNCTION rechazar_modificacion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'RI-22: la tabla % es de solo insercion', TG_TABLE_NAME
        USING ERRCODE = 'check_violation';
END;
$$;

CREATE TRIGGER ri22_validacion BEFORE UPDATE OR DELETE ON validacion_presupuestal
    FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion();
CREATE TRIGGER ri22_ajuste BEFORE UPDATE OR DELETE ON ajuste_requerimiento
    FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion();
CREATE TRIGGER ri22_decision BEFORE UPDATE OR DELETE ON decision_presupuesto
    FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion();
CREATE TRIGGER ri22_historial BEFORE UPDATE OR DELETE ON historial_etapa
    FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion();
CREATE TRIGGER ri22_bitacora BEFORE UPDATE OR DELETE ON bitacora
    FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion();

-- RI-14: el monto estimado es siempre la suma de cantidad x precio de sus ítems.
-- Es diferido: se verifica al confirmar la transacción, cuando ya existen los ítems.
CREATE FUNCTION verificar_monto_requerimiento() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_id INTEGER := COALESCE(NEW.id_requerimiento, OLD.id_requerimiento);
    v_monto NUMERIC(14,2);
    v_suma NUMERIC(14,2);
BEGIN
    SELECT monto_estimado INTO v_monto FROM requerimiento WHERE id_requerimiento = v_id;
    IF v_monto IS NULL THEN
        RETURN NULL;
    END IF;
    SELECT COALESCE(ROUND(SUM(cantidad * precio_unitario_ref), 2), 0) INTO v_suma
        FROM requerimiento_item WHERE id_requerimiento = v_id;
    IF v_suma <> v_monto THEN
        RAISE EXCEPTION 'RI-14: monto estimado % distinto de la suma de items % (requerimiento %)',
            v_monto, v_suma, v_id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER ri14_monto_requerimiento
    AFTER INSERT OR UPDATE OF monto_estimado ON requerimiento
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verificar_monto_requerimiento();
CREATE CONSTRAINT TRIGGER ri14_monto_items
    AFTER INSERT OR UPDATE OR DELETE ON requerimiento_item
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verificar_monto_requerimiento();
"""


def upgrade() -> None:
    op.execute(DDL_TABLAS)
    op.execute(DDL_INDICES)
    op.execute(DDL_DISPARADORES)
    # Seguridad a nivel de fila activada en todas las tablas, sin políticas de acceso público
    # (Tabla 1 de la Práctica 6). La API automática de Supabase queda sin acceso a los datos.
    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for tabla in reversed(TABLAS):
        op.execute(f"DROP TABLE IF EXISTS {tabla} CASCADE")
    op.execute("DROP SEQUENCE IF EXISTS seq_codigo_requerimiento")
    op.execute("DROP FUNCTION IF EXISTS rechazar_modificacion()")
    op.execute("DROP FUNCTION IF EXISTS verificar_monto_requerimiento()")
