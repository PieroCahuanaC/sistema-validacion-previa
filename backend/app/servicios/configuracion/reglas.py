"""P14. Configurar reglas del semáforo (CU-12, RF-03, RNF-04; Tabla 15 de la Práctica 7).

El Jefe de Presupuesto cambia los parámetros de la regla sin tocar el código. Cada cambio crea
una versión nueva y cierra la anterior (vigente_hasta); nunca se edita una versión, porque
cada validación guarda el id de la regla con que se calculó (R14) y debe poder explicarse
después con esos mismos parámetros. Solo hay una versión vigente a la vez (índice I-14).
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import ErrorNegocio
from app.core.reloj import Reloj
from app.esquemas.configuracion import (
    CambioParametro,
    ParametrosSemaforo,
    ReglasSalida,
    VersionRegla,
)
from app.modelos.configuracion import ReglaSemaforo
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto

if TYPE_CHECKING:  # sin importar la conexión: las pruebas unitarias no usan BD
    from app.seguridad.dependencias import UsuarioActual


ETIQUETAS = {
    "umbral_disponibilidad_pct": "Umbral de disponibilidad (%)",
    "columna_comparacion": "Columna que se resta del PIM",
    "tratamiento_no_previsto_pac": "Tratamiento de lo no previsto en el PAC",
    "antiguedad_maxima_dias": "Antigüedad máxima del dato (días)",
    "valor_uit": "Valor de la UIT (S/)",
}


def _normalizar(parametros: dict) -> dict:
    """Parámetros en una forma comparable (la semilla guarda la UIT como 5500.0)."""
    p = ParametrosSemaforo.model_validate(parametros)
    return {
        "umbral_disponibilidad_pct": p.umbral_disponibilidad_pct,
        "columna_comparacion": p.columna_comparacion,
        "tratamiento_no_previsto_pac": p.tratamiento_no_previsto_pac,
        "antiguedad_maxima_dias": p.antiguedad_maxima_dias,
        "valor_uit": str(p.valor_uit.quantize(Decimal("0.01"))),
    }


def _cambios(anterior: dict, nuevo: dict) -> list[CambioParametro]:
    a, n = _normalizar(anterior), _normalizar(nuevo)
    return [CambioParametro(parametro=clave, etiqueta=ETIQUETAS[clave], anterior=str(a[clave]),
                            nuevo=str(n[clave]))
            for clave in ETIQUETAS if a[clave] != n[clave]]


class ServicioReglas:
    def __init__(self, sesion: Session, reloj: Reloj, contexto: Contexto | None = None) -> None:
        self._sesion = sesion
        self._reloj = reloj
        self._contexto = contexto

    def consultar(self) -> ReglasSalida:
        versiones = list(self._sesion.scalars(
            select(ReglaSemaforo).order_by(ReglaSemaforo.vigente_desde, ReglaSemaforo.id_regla)))
        vigente = next((v for v in versiones if v.vigente_hasta is None), None)
        if vigente is None:
            raise ErrorNegocio(503, "Servicio no disponible", "No hay una regla vigente.")
        historial = []
        for indice, version in enumerate(versiones):
            previa = versiones[indice - 1] if indice else None
            historial.append(VersionRegla(
                id_regla=version.id_regla, vigente_desde=version.vigente_desde,
                vigente_hasta=version.vigente_hasta,
                parametros=ParametrosSemaforo.model_validate(version.parametros),
                cambios=_cambios(previa.parametros, version.parametros) if previa else [],
                registrado_por="Jefe de Presupuesto" if previa else "Carga inicial del sistema"))
        historial.reverse()  # la versión más reciente primero
        return ReglasSalida(
            id_regla=vigente.id_regla, vigente_desde=vigente.vigente_desde,
            parametros=ParametrosSemaforo.model_validate(vigente.parametros), historial=historial)

    def guardar_version(self, datos: ParametrosSemaforo, usuario: "UsuarioActual") -> ReglasSalida:
        momento: datetime = self._reloj()
        vigente = self._sesion.scalar(
            select(ReglaSemaforo).where(ReglaSemaforo.vigente_hasta.is_(None)).with_for_update())
        if vigente is None:
            raise ErrorNegocio(503, "Servicio no disponible", "No hay una regla vigente.")
        nuevos = datos.a_json()
        cambios = _cambios(vigente.parametros, nuevos)
        if not cambios:
            raise ErrorNegocio(409, "Sin cambios",
                               "Los valores son iguales a los de la versión vigente; no se creó "
                               "una versión nueva.")
        if momento <= vigente.vigente_desde:  # RI-10: vigente_hasta > vigente_desde
            raise ErrorNegocio(409, "Conflicto de versiones",
                               "La versión vigente se registró en este mismo instante. "
                               "Vuelva a intentarlo.")
        vigente.vigente_hasta = momento
        self._sesion.flush()  # primero se cierra la vigente: solo puede haber una (I-14)
        nueva = ReglaSemaforo(parametros=nuevos, vigente_desde=momento)
        self._sesion.add(nueva)
        self._sesion.flush()
        if self._contexto is not None:
            bitacora.registrar(
                self._sesion, momento, self._contexto, "CONFIG_REGLA", "EXITO",
                id_usuario=usuario.id_usuario, id_rol=usuario.id_rol, recurso_tipo="REGLA",
                recurso_id=nueva.id_regla,
                detalle={"version_anterior": vigente.id_regla,
                         "cambios": {c.parametro: {"anterior": c.anterior, "nuevo": c.nuevo}
                                     for c in cambios}})
        self._sesion.commit()
        return self.consultar()
