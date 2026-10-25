"""Endpoints del incremento 1: registro y consulta del requerimiento, metas y PAC.

Cada endpoint solo valida la entrada (DTO), verifica el rol y delega en el servicio.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import obtener_sesion
from app.core.reloj import Reloj, fecha_local, obtener_reloj
from app.esquemas.requerimiento import (
    MetaSalida,
    PacItemSalida,
    RequerimientoDetalle,
    RequerimientoEntrada,
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
    _, parametros = servicio.regla_vigente()
    return construir_detalle(sesion, requerimiento, parametros)


@router.get("/metas", response_model=list[MetaSalida])
def metas(_: AreaUsuaria, sesion: SesionDep, reloj: RelojDep) -> list[MetaSalida]:
    """Metas activas del ejercicio vigente con su saldo presupuestal disponible referencial."""
    _, parametros = ServicioValidacion(sesion, reloj).regla_vigente()
    return listar_metas(sesion, fecha_local(reloj()).year, parametros)


@router.get("/pac-items", response_model=list[PacItemSalida])
def pac_items(_: AreaUsuaria, sesion: SesionDep, reloj: RelojDep) -> list[PacItemSalida]:
    """Ítems del PAC vigente (última carga exitosa del SEACE)."""
    return listar_pac(sesion, fecha_local(reloj()).year)
