"""Endpoints del trámite del expediente (Práctica 5, contrato de la API; Práctica 7, P05,
P07, P08, P11 y P17).

Cada endpoint declara los roles que pueden invocarlo (rol por endpoint); la pertenencia del
recurso y el rol por transición los verifica la capa de servicios (sección 3 de la P5).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import obtener_sesion
from app.core.reloj import Reloj, obtener_reloj
from app.esquemas.tramite import (
    AjusteEntrada,
    AlertasSalida,
    BandejaFila,
    CambioEtapaEntrada,
    CambioEtapaSalida,
    DecisionEntrada,
    DecisionSalida,
    HistorialSalida,
    MiRequerimientoFila,
    ResultadoAjuste,
)
from app.modelos.catalogos import Estado
from app.seguridad.dependencias import UsuarioActual, contexto_peticion, requiere_rol
from app.servicios.seguridad.bitacora import Contexto
from app.servicios.trazabilidad.historial import construir_historial
from app.servicios.trazabilidad.maquina import MaquinaEstados
from app.servicios.validacion.ajuste import ServicioAjuste
from app.servicios.validacion.decision import ServicioDecision
from app.servicios.validacion.listas import (
    alertas_presupuesto,
    bandeja_gerencia,
    mis_requerimientos,
)
from app.servicios.validacion.servicio import ServicioValidacion

router = APIRouter(tags=["trámite del expediente"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]
ContextoDep = Annotated[Contexto, Depends(contexto_peticion)]
AreaUsuaria = Annotated[UsuarioActual, Depends(requiere_rol("AU"))]
Gerencia = Annotated[UsuarioActual, Depends(requiere_rol("GA"))]
Presupuesto = Annotated[UsuarioActual, Depends(requiere_rol("JP"))]
RolFuncional = Annotated[UsuarioActual, Depends(requiere_rol("AU", "GA", "JL", "JP"))]


@router.get("/requerimientos", response_model=list[MiRequerimientoFila])
def listar_mis_requerimientos(
    usuario: AreaUsuaria, sesion: SesionDep, reloj: RelojDep,
    semaforo: Annotated[str | None, Query(pattern="^(VERDE|AMBAR|ROJO)$")] = None,
    estado: Annotated[str | None, Query(max_length=30)] = None,
    buscar: Annotated[str | None, Query(max_length=15)] = None,
    cuello_de_botella: bool = False,
) -> list[MiRequerimientoFila]:
    """Requerimientos de la unidad del usuario, incluidos los cerrados (P17; CU-04).

    Los filtros coinciden con las tarjetas de la P02, que abren esta lista ya filtrada (H7).
    """
    return mis_requerimientos(sesion, usuario.id_unidad, semaforo, estado, buscar,
                              cuello_de_botella, reloj())


@router.patch("/requerimientos/{id_requerimiento}/etapa", response_model=CambioEtapaSalida)
def cambiar_etapa(
    id_requerimiento: int, datos: CambioEtapaEntrada, usuario: RolFuncional, sesion: SesionDep,
    reloj: RelojDep, contexto: ContextoDep,
) -> CambioEtapaSalida:
    """Registra un cambio de etapa permitido por la máquina de estados (CU-10, RF-05).

    Responde 403 si la transición le corresponde a otro rol y 409 si no está permitida desde
    el estado actual o no se cumple su condición de negocio.
    """
    requerimiento, origen, registro = MaquinaEstados(sesion, reloj, contexto).cambiar_desde_api(
        id_requerimiento, datos.destino, datos.observacion, usuario)
    estado = sesion.get(Estado, requerimiento.id_estado_actual)
    anterior = sesion.scalar(select(Estado).where(Estado.codigo == origen))
    return CambioEtapaSalida(requerimiento_id=requerimiento.id_requerimiento,
                             codigo=requerimiento.codigo, estado_anterior=anterior.nombre,
                             estado_actual=estado.nombre, fecha_hora=registro.fecha_hora)


@router.post("/requerimientos/{id_requerimiento}/ajustes", response_model=ResultadoAjuste)
def aplicar_ajuste(
    id_requerimiento: int, datos: AjusteEntrada, usuario: AreaUsuaria, sesion: SesionDep,
    reloj: RelojDep, contexto: ContextoDep,
) -> ResultadoAjuste:
    """Aplica el ajuste sugerido ante un semáforo rojo y revalida (CU-05, RF-04; P05)."""
    return ServicioAjuste(sesion, reloj, contexto).aplicar(id_requerimiento, datos, usuario)


@router.get("/requerimientos/{id_requerimiento}/historial", response_model=HistorialSalida)
def historial(
    id_requerimiento: int, usuario: RolFuncional, sesion: SesionDep, reloj: RelojDep,
) -> HistorialSalida:
    """Línea de tiempo del expediente con duración y plazo de cada etapa (P07; CU-10)."""
    requerimiento = ServicioValidacion(sesion, reloj).obtener_para_usuario(id_requerimiento,
                                                                           usuario)
    return construir_historial(sesion, requerimiento, reloj())


@router.get("/bandeja", response_model=list[BandejaFila])
def bandeja(_: Gerencia, sesion: SesionDep, reloj: RelojDep) -> list[BandejaFila]:
    """Requerimientos enviados con semáforo vigente verde por aprobar (P08; CU-11, RF-13)."""
    return bandeja_gerencia(sesion, reloj())


@router.get("/alertas", response_model=AlertasSalida)
def alertas(_: Presupuesto, sesion: SesionDep, reloj: RelojDep) -> AlertasSalida:
    """Requerimientos en ámbar sin decisión y en rojo (P11; CU-06, RF-09)."""
    return alertas_presupuesto(sesion, reloj())


@router.post("/alertas/{id_requerimiento}/decision", response_model=DecisionSalida)
def decidir(
    id_requerimiento: int, datos: DecisionEntrada, usuario: Presupuesto, sesion: SesionDep,
    reloj: RelojDep, contexto: ContextoDep,
) -> DecisionSalida:
    """Confirma o deniega la disponibilidad de un ámbar (P11; CU-06, RF-09)."""
    return ServicioDecision(sesion, reloj, contexto).registrar(id_requerimiento, datos, usuario)
