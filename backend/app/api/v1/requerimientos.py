"""Endpoints de la validación presupuestal: registro en dos pasos, consulta, metas y PAC.

Cada endpoint solo valida la entrada (DTO), verifica el rol y delega en el servicio.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import obtener_sesion
from app.core.reloj import Reloj, fecha_local, obtener_reloj
from app.esquemas.requerimiento import (
    EnvioEntrada,
    MetaSalida,
    PacItemSalida,
    Paso2Entrada,
    ReglaVigenteSalida,
    RequerimientoDetalle,
    RequerimientoEntrada,
    ResultadoEnvio,
    ResultadoRegistro,
)
from app.seguridad.dependencias import UsuarioActual, requiere_rol
from app.servicios.validacion.consultas import listar_metas, listar_pac
from app.servicios.validacion.detalle import construir_detalle
from app.servicios.validacion.servicio import ServicioValidacion

router = APIRouter(tags=["validación presupuestal"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]
AreaUsuaria = Annotated[UsuarioActual, Depends(requiere_rol("AU"))]


@router.post("/requerimientos", status_code=status.HTTP_201_CREATED,
             response_model=ResultadoRegistro)
def registrar_requerimiento(
    datos: RequerimientoEntrada, usuario: AreaUsuaria, sesion: SesionDep, reloj: RelojDep
) -> ResultadoRegistro:
    """Registra un requerimiento y obtiene su semáforo (CU-03, CU-01; RF-01 a RF-03).

    Un semáforo rojo o ámbar se responde con 201: es un resultado válido, no un error.
    """
    return ServicioValidacion(sesion, reloj).registrar(datos, usuario)


@router.get("/requerimientos/{id_requerimiento}", response_model=RequerimientoDetalle)
def detalle_requerimiento(
    id_requerimiento: int, usuario: AreaUsuaria, sesion: SesionDep, reloj: RelojDep
) -> RequerimientoDetalle:
    """Detalle del requerimiento con su semáforo y las etapas del trámite (CU-04)."""
    servicio = ServicioValidacion(sesion, reloj)
    requerimiento = servicio.obtener_para_usuario(id_requerimiento, usuario)
    return construir_detalle(sesion, requerimiento)


@router.put("/requerimientos/{id_requerimiento}/paso-2", response_model=RequerimientoDetalle)
def guardar_paso_2(
    id_requerimiento: int, datos: Paso2Entrada, usuario: AreaUsuaria, sesion: SesionDep,
    reloj: RelojDep,
) -> RequerimientoDetalle:
    """Guarda el paso 2 sin enviar: especificaciones, plazo y lugar de entrega (P03, paso 2).

    Responde 409 si el semáforo vigente no es verde o si el requerimiento ya fue enviado.
    """
    requerimiento = ServicioValidacion(sesion, reloj).guardar_paso_2(id_requerimiento, datos,
                                                                     usuario)
    return construir_detalle(sesion, requerimiento)


@router.post("/requerimientos/{id_requerimiento}/envio", response_model=ResultadoEnvio)
def enviar_requerimiento(
    id_requerimiento: int, datos: EnvioEntrada, usuario: AreaUsuaria, sesion: SesionDep,
    reloj: RelojDep,
) -> ResultadoEnvio:
    """Envía el requerimiento a la Gerencia de Administración (P03, paso 2; RI-20 y RI-28).

    Exige semáforo vigente verde, el paso 2 completo y los tres documentos marcados.
    """
    return ServicioValidacion(sesion, reloj).enviar(id_requerimiento, datos, usuario)


@router.get("/metas", response_model=list[MetaSalida])
def metas(_: AreaUsuaria, sesion: SesionDep, reloj: RelojDep) -> list[MetaSalida]:
    """Metas activas del ejercicio vigente con su saldo presupuestal disponible referencial."""
    _, parametros = ServicioValidacion(sesion, reloj).regla_vigente()
    return listar_metas(sesion, fecha_local(reloj()).year, parametros)


@router.get("/pac-items", response_model=list[PacItemSalida])
def pac_items(_: AreaUsuaria, sesion: SesionDep, reloj: RelojDep) -> list[PacItemSalida]:
    """Ítems del PAC vigente (última carga exitosa del SEACE)."""
    return listar_pac(sesion, fecha_local(reloj()).year)


@router.get("/regla-vigente", response_model=ReglaVigenteSalida)
def regla_vigente(_: AreaUsuaria, sesion: SesionDep, reloj: RelojDep) -> ReglaVigenteSalida:
    """Tope de 8 UIT de la regla vigente, para validar el monto en la pantalla (RNF-04)."""
    _, parametros = ServicioValidacion(sesion, reloj).regla_vigente()
    return ReglaVigenteSalida(valor_uit=parametros.valor_uit, tope_8_uit=parametros.tope_8_uit,
                              antiguedad_maxima_dias=parametros.antiguedad_maxima_dias)
