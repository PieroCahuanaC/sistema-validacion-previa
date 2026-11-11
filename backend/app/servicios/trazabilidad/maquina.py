"""Máquina de estados del expediente (CU-10, RF-05; Figura 5 y sección 1.6 de la Práctica 5).

Cada cambio de estado se verifica en dos niveles antes de guardarse:
  1. la transición existe en el catálogo (Tabla 15 de la Práctica 6) y el rol del usuario es
     el que puede registrarla (rol por transición, sección 3 de la Práctica 5);
  2. la guarda de negocio de esa transición se cumple (por ejemplo, la Gerencia solo aprueba
     requerimientos enviados con semáforo vigente verde).
Si ambos se cumplen, se actualiza el estado actual (R17), se agrega el registro del historial
(R18 a R20, de solo inserción por RI-22) y se deja constancia en la bitácora, todo en la
misma transacción.
"""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import DatosNoValidos, ErrorNegocio, NoEncontrado
from app.core.reloj import Reloj
from app.modelos.catalogos import Estado, Rol, Transicion
from app.modelos.requerimiento import HistorialEtapa, Requerimiento
from app.seguridad.dependencias import UsuarioActual
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto
from app.servicios.validacion.situacion import Situacion, situacion
from app.servicios.validacion.vigencia import SemaforoVigente

Guarda = Callable[[Situacion], str | None]


def _aprobar(s: Situacion) -> str | None:
    if not s.en_bandeja_de_gerencia:
        return ("Solo se aprueban requerimientos enviados por el Área Usuaria con semáforo "
                "vigente verde.")
    return None


def _observar_en_gerencia(s: Situacion) -> str | None:
    if not s.enviado:
        return "Solo se observan requerimientos enviados a la Gerencia de Administración."
    return None


def _anular(s: Situacion) -> str | None:
    if not s.puede_anular:
        return ("Solo se anula un requerimiento sin salida: en rojo sin ajuste aceptado "
                "(opción Ninguna) o en ámbar con disponibilidad denegada (RI-25).")
    return None


def _sin_condicion(_: Situacion) -> str | None:
    return None


def _certificar(s: Situacion) -> str | None:
    if s.vigente == SemaforoVigente.AMBAR_PENDIENTE:
        return ("El semáforo está en ámbar: confirme primero la disponibilidad en el Panel de "
                "alertas (P11).")
    if s.vigente != SemaforoVigente.VERDE:
        return ("No hay disponibilidad presupuestal confirmada: devuelva el expediente o "
                "anúlelo por falta de disponibilidad.")
    return None


# Transiciones que se registran con PATCH /requerimientos/{id}/etapa y su guarda de negocio.
# Las que exigen datos propios (revisión documental, cuadro comparativo, certificación y
# orden) se registran desde sus pantallas y se agregan aquí cuando existen.
GUARDAS: dict[tuple[str, str], Guarda] = {
    ("REGISTRADO", "APROBADO"): _aprobar,
    ("REGISTRADO", "OBSERVADO"): _observar_en_gerencia,
    ("OBSERVADO", "REGISTRADO"): _sin_condicion,
    ("REGISTRADO", "ANULADO"): _anular,
    # Incremento 3B: certificación (P12) y orden (P13).
    ("CUADRO_REGISTRADO", "CERTIFICADO"): _certificar,
    ("CUADRO_REGISTRADO", "DOCUMENTACION_VALIDADA"): _sin_condicion,
    ("CUADRO_REGISTRADO", "ANULADO"): _sin_condicion,
    ("CERTIFICADO", "ORDEN_EMITIDA"): _sin_condicion,
}

# Además de las devoluciones, exigen observación: la anulación por falta de disponibilidad
# que registra Presupuesto (cambio 16 de la Práctica 7) debe dejar su motivo.
OBSERVACION_OBLIGATORIA = {("CUADRO_REGISTRADO", "ANULADO")}


class MaquinaEstados:
    def __init__(self, sesion: Session, reloj: Reloj, contexto: Contexto) -> None:
        self._sesion = sesion
        self._reloj = reloj
        self._contexto = contexto

    def obtener(self, id_requerimiento: int, usuario: UsuarioActual) -> Requerimiento:
        """Obtiene el requerimiento para consulta, con la misma regla de pertenencia."""
        requerimiento = self._sesion.get(Requerimiento, id_requerimiento)
        if requerimiento is None or (
            usuario.codigo_rol == "AU" and requerimiento.id_unidad != usuario.id_unidad
        ):
            raise NoEncontrado("El requerimiento no existe.")
        return requerimiento

    def bloquear(self, id_requerimiento: int, usuario: UsuarioActual) -> Requerimiento:
        """Obtiene el requerimiento con bloqueo de fila, para que dos usuarios no registren a
        la vez dos cambios sobre el mismo expediente. El Área Usuaria solo accede a los de su
        unidad; para el resto responde 404 y no 403, para no revelar que existe (OWASP A01)."""
        requerimiento = self._sesion.get(Requerimiento, id_requerimiento, with_for_update=True)
        if requerimiento is None or (
            usuario.codigo_rol == "AU" and requerimiento.id_unidad != usuario.id_unidad
        ):
            raise NoEncontrado("El requerimiento no existe.")
        return requerimiento

    def cambiar_desde_api(
        self, id_requerimiento: int, destino: str, observacion: str | None,
        usuario: UsuarioActual,
    ) -> tuple[Requerimiento, str, HistorialEtapa]:
        requerimiento = self.bloquear(id_requerimiento, usuario)
        actual = situacion(self._sesion, requerimiento)
        origen = actual.codigo_estado
        transicion = self.verificar(requerimiento, destino, usuario)
        guarda = GUARDAS.get((origen, destino))
        if guarda is None:
            raise ErrorNegocio(409, "Conflicto",
                               "Este cambio de etapa se registra desde su propia pantalla.")
        motivo = guarda(actual)
        if motivo:
            raise ErrorNegocio(409, "Conflicto", motivo)
        if (origen, destino) in OBSERVACION_OBLIGATORIA and not (observacion or "").strip():
            raise DatosNoValidos("Indique el motivo: la observación es obligatoria.")
        registro = self.registrar(requerimiento, transicion, destino, observacion, usuario)
        self._sesion.commit()
        return requerimiento, origen, registro

    def verificar(self, requerimiento: Requerimiento, destino: str,
                  usuario: UsuarioActual) -> Transicion:
        """Nivel 1: la transición existe y el rol del usuario es el que la registra."""
        origen = self._sesion.get(Estado, requerimiento.id_estado_actual)
        estado_destino = self._estado(destino)
        transicion = self._sesion.scalar(select(Transicion).where(
            Transicion.id_estado_origen == origen.id_estado,
            Transicion.id_estado_destino == estado_destino.id_estado))
        if transicion is None:
            raise ErrorNegocio(409, "Conflicto",
                               f"No se puede pasar de {origen.nombre} a {estado_destino.nombre}.")
        rol = self._sesion.get(Rol, transicion.id_rol)
        if rol.codigo != usuario.codigo_rol:
            bitacora.registrar(
                self._sesion, self._reloj(), self._contexto, "ACCESO_DENEGADO", "DENEGADO",
                id_usuario=usuario.id_usuario, id_rol=usuario.id_rol,
                recurso_tipo="REQUERIMIENTO", recurso_id=requerimiento.id_requerimiento,
                detalle={"motivo": "rol_por_transicion", "origen": origen.codigo,
                         "destino": destino})
            self._sesion.commit()
            raise ErrorNegocio(403, "Acceso denegado",
                               f"Este cambio de etapa le corresponde a: {rol.nombre}.")
        return transicion

    def registrar(
        self, requerimiento: Requerimiento, transicion: Transicion, destino: str,
        observacion: str | None, usuario: UsuarioActual, momento: datetime | None = None,
    ) -> HistorialEtapa:
        """Nivel 2 ya verificado: guarda el cambio, el historial y la bitácora (sin commit)."""
        observacion = (observacion or "").strip() or None
        if transicion.tipo == "DEVOLUCION" and observacion is None:
            raise DatosNoValidos("La observación es obligatoria para devolver el expediente.")
        momento = momento or self._reloj()
        origen = self._sesion.get(Estado, requerimiento.id_estado_actual)
        estado_destino = self._estado(destino)
        requerimiento.id_estado_actual = estado_destino.id_estado
        registro = HistorialEtapa(
            id_requerimiento=requerimiento.id_requerimiento, id_estado=estado_destino.id_estado,
            id_rol=usuario.id_rol, fecha_hora=momento, observacion=observacion)
        self._sesion.add(registro)
        self._sesion.flush()
        bitacora.registrar(
            self._sesion, momento, self._contexto, "CAMBIO_ETAPA", "EXITO",
            id_usuario=usuario.id_usuario, id_rol=usuario.id_rol,
            recurso_tipo="REQUERIMIENTO", recurso_id=requerimiento.id_requerimiento,
            detalle={"origen": origen.codigo, "destino": destino, "tipo": transicion.tipo})
        return registro

    def _estado(self, codigo: str) -> Estado:
        estado = self._sesion.scalar(select(Estado).where(Estado.codigo == codigo))
        if estado is None:
            raise DatosNoValidos(f"El estado {codigo} no existe.")
        return estado
