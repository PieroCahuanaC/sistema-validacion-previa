#!/bin/sh
# Prueba de carga de la base de datos (Práctica 9, Tabla 10).
# Ejecuta saldo.sql con pgbench a varios niveles de consultas simultáneas y guarda, por nivel,
# la salida de pgbench y el registro de cada transacción (para calcular el p95).
#
# Variables:
#   BD_URL     cadena de conexión (admite la forma de SQLAlchemy, postgresql+psycopg://...).
#              Se lee del entorno; nunca se imprime.
#   NIVELES    consultas simultáneas a probar (por defecto "10 25 50 100 200 400").
#   DURACION   segundos por nivel (por defecto 30).
#   SALIDA     carpeta de resultados (por defecto ./resultados/bd).
set -u

if [ -z "${BD_URL:-}" ]; then
    echo "Falta la variable BD_URL." >&2
    exit 1
fi
NIVELES="${NIVELES:-10 25 50 100 200 400}"
DURACION="${DURACION:-30}"
SALIDA="${SALIDA:-./resultados/bd}"
DIR=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$SALIDA"

# libpq no entiende el sufijo del controlador de SQLAlchemy.
URL=$(printf '%s' "$BD_URL" | sed 's#^postgresql+[a-z0-9]*://#postgresql://#')

ANIO=$(psql "$URL" -Atc "SELECT extract(year FROM now() AT TIME ZONE 'America/Lima')::int") || {
    echo "No se pudo conectar a la base de datos." >&2
    exit 1
}
NMETAS=$(psql "$URL" -Atc "SELECT count(*) FROM meta_presupuestal WHERE anio_fiscal = $ANIO AND activa")
if [ "$NMETAS" -eq 0 ]; then
    echo "No hay metas activas para $ANIO." >&2
    exit 1
fi
echo "Ejercicio $ANIO, $NMETAS metas activas, $DURACION s por nivel."
printf 'anio=%s\nmetas=%s\nduracion=%s\n' "$ANIO" "$NMETAS" "$DURACION" > "$SALIDA/contexto.txt"

for N in $NIVELES; do
    HILOS=$N
    [ "$HILOS" -gt 4 ] && HILOS=4
    echo "== $N consultas simultáneas =="
    rm -f "$SALIDA"/bd_c"$N".*
    # -n: sin VACUUM (no se crean las tablas de pgbench); -l: una línea por transacción.
    pgbench "$URL" -n -c "$N" -j "$HILOS" -T "$DURACION" -f "$DIR/saldo.sql" \
        -D anio="$ANIO" -D nmetas="$NMETAS" -l --log-prefix="$SALIDA/bd_c$N" \
        > "$SALIDA/bd_c$N.txt" 2>&1
    echo "codigo_salida=$?" >> "$SALIDA/bd_c$N.txt"
    grep -E "processed|failed|latency average|tps|aborted|error" "$SALIDA/bd_c$N.txt" | head -6
    sleep 5  # deja que el pooler libere las conexiones antes del siguiente nivel
done
