"""Decisión del Jefe de Presupuesto sobre un semáforo ámbar (CU-06, RF-09; pantalla P11).

El ámbar señala que el sistema no puede afirmar la disponibilidad (dato ausente o
desactualizado, o requerimiento no previsto en el PAC). Presupuesto confirma o deniega la
disponibilidad con su sustento; la decisión es única por validación (R16) y no se modifica
(RI-22). Confirmada, el semáforo vigente pasa a verde (RI-20); denegada, el Área Usuaria
solo puede anular el requerimiento.
"""

from sqlalchemy.orm import Session

from app.core.errores import DatosNoValidos, ErrorNegocio
from app.core.reloj import Reloj
from app.esquemas.tramite import DecisionEntrada, DecisionSalida
from app.modelos.requerimiento import DecisionPresupuesto
from app.seguridad.dependencias import UsuarioActual
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto
from app.servicios.trazabilidad.maquina import MaquinaEstados
from app.servicios.validacion.situacion import situacion


class ServicioDecision:
    def __init__(self, sesion: Session, reloj: Reloj, contexto: Contexto) -> None:
        self._sesion = sesion
        self._reloj = reloj
        self._contexto = contexto

    def registrar(self, id_requerimiento: int, datos: DecisionEntrada,
                  usuario: UsuarioActual) -> DecisionSalida:
        requerimiento = MaquinaEstados(self._sesion, self._reloj, self._contexto).bloquear(
            id_requerimiento, usuario)
        actual = situacion(self._sesion, requerimiento)
        if not actual.ambar_sin_decision:
            raise ErrorNegocio(409, "Conflicto",
                               "Solo se decide sobre la última validación en ámbar que aún no "
                               "tiene decisión; una vez registrada no se modifica.")
        sustento = (datos.sustento or "").strip() or None
        if datos.resultado == "DENEGADA" and sustento is None:
            raise DatosNoValidos("El sustento es obligatorio para denegar la disponibilidad.")
        momento = self._reloj()
        decision = DecisionPresupuesto(id_validacion=actual.validacion.id_validacion,
                                       resultado=datos.resultado, sustento=sustento,
                                       fecha_hora=momento)
        self._sesion.add(decision)
        self._sesion.flush()
        bitacora.registrar(
            self._sesion, momento, self._contexto, "DECISION_AMBAR", "EXITO",
            id_usuario=usuario.id_usuario, id_rol=usuario.id_rol,
            recurso_tipo="REQUERIMIENTO", recurso_id=requerimiento.id_requerimiento,
            detalle={"resultado": datos.resultado, "motivo": actual.validacion.motivo})
        self._sesion.commit()
        return DecisionSalida(
            requerimiento_id=requerimiento.id_requerimiento, codigo=requerimiento.codigo,
            resultado=datos.resultado, sustento=sustento, fecha_hora=momento,
            semaforo_vigente=str(situacion(self._sesion, requerimiento).vigente))
