"""P15. Estado de la base presupuestal y carga CSV de respaldo (RF-14; plan de respuesta del
riesgo R01; Tabla 16 de la Práctica 7).

Muestra, para la Consulta Amigable del MEF y para el SEACE, la última ejecución, la fecha de
corte y el resultado, con su historial. La carga manual sigue dos pasos: primero se valida el
archivo y se muestra una vista previa sin escribir nada; luego se carga, y el servidor vuelve
a validarlo completo antes de registrar (H5: no se carga un archivo sin validarlo).
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import obtener_configuracion
from app.core.errores import DatosNoValidos, ErrorNegocio
from app.core.reloj import Reloj, fecha_local
from app.esquemas.configuracion import (
    BasePresupuestalSalida,
    CargaEntrada,
    CargaSalida,
    EstadoFuente,
    ResultadoCarga,
    ValidacionCargaSalida,
)
from app.extraccion.carga_csv import COLUMNAS, cargar_csv, es_la_mas_reciente, validar_csv
from app.modelos.presupuesto import CargaDatos, MetaPresupuestal, PacItem, SaldoMeta
from app.repositorios.catalogos import RepositorioCatalogos
from app.repositorios.presupuesto import RepositorioPresupuesto
from app.seguridad.dependencias import UsuarioActual
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto

NOMBRES = {
    "MEF": "Consulta Amigable del MEF (saldos por meta)",
    "SEACE": "SEACE (Plan Anual de Contrataciones)",
}
MAX_FILAS = 5000
MAX_ERRORES_MOSTRADOS = 50
FILAS_VISTA_PREVIA = 20
CARGAS_EN_HISTORIAL = 30


def _salida(carga: CargaDatos | None) -> CargaSalida | None:
    if carga is None:
        return None
    return CargaSalida(
        id_carga=carga.id_carga, fuente=carga.fuente, origen=carga.origen,
        anio_fiscal=carga.anio_fiscal, fecha_ejecucion=carga.fecha_ejecucion,
        fecha_corte=carga.fecha_corte, resultado=carga.resultado,
        detalle_error=carga.detalle_error)


def _fecha(valor: date | datetime) -> str:
    return valor.strftime("%d/%m/%Y")


class ServicioBasePresupuestal:
    def __init__(self, sesion: Session, reloj: Reloj, contexto: Contexto | None = None) -> None:
        self._sesion = sesion
        self._reloj = reloj
        self._contexto = contexto
        self._presupuesto = RepositorioPresupuesto(sesion)

    def _antiguedad_maxima(self) -> int:
        regla = RepositorioCatalogos(self._sesion).regla_vigente()
        if regla is None:
            raise ErrorNegocio(503, "Servicio no disponible", "No hay una regla vigente.")
        return int(regla.parametros["antiguedad_maxima_dias"])

    # --- Estado de las fuentes e historial --------------------------------------------------
    def estado(self) -> BasePresupuestalSalida:
        ahora = self._reloj()
        anio = fecha_local(ahora).year
        antiguedad = self._antiguedad_maxima()
        fuentes = []
        for fuente in ("MEF", "SEACE"):
            ultima = self._sesion.scalar(
                select(CargaDatos)
                .where(CargaDatos.fuente == fuente, CargaDatos.anio_fiscal == anio)
                .order_by(CargaDatos.fecha_ejecucion.desc(), CargaDatos.id_carga.desc()).limit(1))
            exitosa = self._presupuesto.ultima_carga_exitosa(fuente, anio)
            dias = None
            desactualizado = fuente == "MEF" and exitosa is None
            if exitosa is not None:
                dias = (fecha_local(ahora) - fecha_local(exitosa.fecha_corte)).days
                # La misma comparación que hace el semáforo (motivo DATO_DESACTUALIZADO).
                desactualizado = fuente == "MEF" and (
                    ahora - exitosa.fecha_corte > timedelta(days=antiguedad))
            fuentes.append(EstadoFuente(
                fuente=fuente, nombre=NOMBRES[fuente], ultima_ejecucion=_salida(ultima),
                ultima_exitosa=_salida(exitosa), dias_desde_corte=dias,
                desactualizado=desactualizado))
        historial = self._sesion.scalars(
            select(CargaDatos).order_by(CargaDatos.fecha_ejecucion.desc(),
                                        CargaDatos.id_carga.desc()).limit(CARGAS_EN_HISTORIAL))
        return BasePresupuestalSalida(
            anio_fiscal=anio, antiguedad_maxima_dias=antiguedad, fuentes=fuentes,
            historial=[_salida(c) for c in historial], columnas=COLUMNAS)

    # --- Validación (vista previa) ---------------------------------------------------------
    def _verificar_fechas(self, datos: CargaEntrada) -> None:
        hoy = fecha_local(self._reloj())
        if datos.anio_fiscal > hoy.year:
            raise DatosNoValidos("El año fiscal no puede ser posterior al año en curso.")
        if datos.fecha_corte > hoy:
            raise DatosNoValidos("La fecha de corte no puede ser posterior a hoy.")
        if datos.fecha_corte.year < datos.anio_fiscal:
            raise DatosNoValidos("La fecha de corte debe pertenecer al año fiscal o ser posterior.")

    def validar(self, datos: CargaEntrada) -> ValidacionCargaSalida:
        self._verificar_fechas(datos)
        resultado = validar_csv(datos.fuente, datos.contenido)
        errores = list(resultado.errores)
        if len(resultado.filas) > MAX_FILAS:
            errores.insert(0, f"El archivo tiene {len(resultado.filas)} filas; el máximo es "
                              f"{MAX_FILAS}.")
        valido = not errores and bool(resultado.filas)
        avisos = self._avisos(datos, resultado.filas) if valido else []
        return ValidacionCargaSalida(
            valido=valido, fuente=datos.fuente, columnas=COLUMNAS[datos.fuente],
            total_filas=len(resultado.filas),
            vista_previa=[{clave: str(valor) for clave, valor in fila.items()}
                          for fila in resultado.filas[:FILAS_VISTA_PREVIA]],
            errores=errores[:MAX_ERRORES_MOSTRADOS], total_errores=len(errores), avisos=avisos)

    def _avisos(self, datos: CargaEntrada, filas: list[dict]) -> list[str]:
        avisos = []
        corte = self._corte(datos.fecha_corte)
        vigente = self._presupuesto.ultima_carga_exitosa(datos.fuente, datos.anio_fiscal)
        if vigente is not None and corte < vigente.fecha_corte:
            avisos.append(
                f"La fecha de corte es anterior a la de la carga vigente "
                f"({_fecha(fecha_local(vigente.fecha_corte))}): esta carga quedará en el "
                "historial, pero no reemplazará los datos con los que se valida.")
            return avisos
        if datos.fuente == "MEF":
            antiguedad = self._antiguedad_maxima()
            if self._reloj() - corte > timedelta(days=antiguedad):
                avisos.append(
                    f"La fecha de corte tiene más de {antiguedad} días: los requerimientos "
                    "que se registren con estos saldos saldrán en ámbar (dato desactualizado).")
            activas = {m.codigo for m in self._sesion.scalars(select(MetaPresupuestal).where(
                MetaPresupuestal.anio_fiscal == datos.anio_fiscal,
                MetaPresupuestal.activa.is_(True)))}
            en_archivo = {f["codigo"] for f in filas}
            nuevas, salen = sorted(en_archivo - activas), sorted(activas - en_archivo)
            if nuevas:
                avisos.append(f"{len(nuevas)} meta(s) nueva(s) se ofrecerán al registrar: "
                              f"{', '.join(nuevas[:10])}{'…' if len(nuevas) > 10 else ''}.")
            if salen:
                avisos.append(f"{len(salen)} meta(s) no figuran en el archivo y dejarán de "
                              f"ofrecerse al registrar: {', '.join(salen[:10])}"
                              f"{'…' if len(salen) > 10 else ''}. Los requerimientos que ya las "
                              "usan se conservan.")
        return avisos

    @staticmethod
    def _corte(fecha: date) -> datetime:
        zona = ZoneInfo(obtener_configuracion().zona_horaria)
        return datetime.combine(fecha, time(0), tzinfo=zona)

    # --- Carga ------------------------------------------------------------------------------
    def cargar(self, datos: CargaEntrada, usuario: UsuarioActual) -> ResultadoCarga:
        self._verificar_fechas(datos)
        momento = self._reloj()
        previa = self.validar(datos)
        if previa.total_filas > MAX_FILAS:
            raise DatosNoValidos(previa.errores[0])
        carga = cargar_csv(self._sesion, datos.fuente, datos.anio_fiscal,
                           self._corte(datos.fecha_corte), datos.contenido,
                           fecha_ejecucion=momento, confirmar=False)
        exitosa = carga.resultado == "EXITOSA"
        modelo = SaldoMeta if datos.fuente == "MEF" else PacItem
        filas = self._sesion.scalar(
            select(func.count()).select_from(modelo).where(modelo.id_carga == carga.id_carga))
        if self._contexto is not None:
            bitacora.registrar(
                self._sesion, momento, self._contexto, "EXTRACCION_DATOS",
                "EXITO" if exitosa else "ERROR", id_usuario=usuario.id_usuario,
                id_rol=usuario.id_rol, recurso_tipo="CARGA", recurso_id=carga.id_carga,
                detalle={"fuente": carga.fuente, "origen": carga.origen,
                         "anio_fiscal": carga.anio_fiscal, "resultado": carga.resultado,
                         "fecha_corte": datos.fecha_corte.isoformat(), "filas": filas})
        vigente = exitosa and es_la_mas_reciente(self._sesion, carga)
        self._sesion.commit()
        if not exitosa:
            raise ErrorNegocio(
                422, "Archivo rechazado",
                "El archivo tiene errores y no se cargó ningún dato. Valídelo y corríjalo.",
                {"errores_archivo": previa.errores, "id_carga": carga.id_carga})
        return ResultadoCarga(carga=_salida(carga), filas=filas, vigente=vigente)
