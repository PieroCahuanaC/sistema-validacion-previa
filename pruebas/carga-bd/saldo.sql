-- Consulta del saldo disponible de una meta (RF-02), la lectura que hace el sistema antes de
-- evaluar el semáforo: regla vigente, última carga exitosa del MEF y saldo de la meta en esa
-- carga, con el disponible calculado según la columna configurada (PIM − Compromiso o
-- PIM − Certificación). Es solo lectura: la prueba no escribe en la base.
-- pgbench la ejecuta con una meta activa al azar por transacción; :anio y :nmetas los fija
-- ejecutar.sh con -D.
\set k random(0, :nmetas - 1)
WITH regla AS (
    SELECT parametros ->> 'columna_comparacion' AS columna
    FROM regla_semaforo
    WHERE vigente_hasta IS NULL
),
meta AS (
    SELECT id_meta
    FROM meta_presupuestal
    WHERE anio_fiscal = :anio AND activa
    ORDER BY codigo
    OFFSET :k LIMIT 1
),
carga AS (
    SELECT id_carga, fecha_corte
    FROM carga_datos
    WHERE fuente = 'MEF' AND resultado = 'EXITOSA' AND anio_fiscal = :anio
    ORDER BY fecha_corte DESC, id_carga DESC
    LIMIT 1
)
SELECT s.pim - CASE WHEN (SELECT columna FROM regla) = 'CERTIFICACION'
                    THEN s.certificacion ELSE s.compromiso_anual END AS disponible,
       c.fecha_corte
FROM saldo_meta s
JOIN carga c ON c.id_carga = s.id_carga
JOIN meta m ON m.id_meta = s.id_meta;
