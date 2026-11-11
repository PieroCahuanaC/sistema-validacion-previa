"""Endpoints de Logística y certificación (P09, P10, P12 y P13; CU-07, CU-08, CU-13 y CU-14).

Los cambios de etapa de la P12 (certificar, devolver o anular) y de la P13 (orden emitida) se
registran con PATCH /requerimientos/{id}/etapa; aquí están las operaciones que además guardan
datos propios: la revisión de documentos y el cuadro comparativo.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_sesion
from app.core.reloj import Reloj, obtener_reloj
from app.esquemas.logistica import (
    BusquedaProveedor,
    CuadroEntrada,
    CuadroResultado,
    CuadroSalida,
    ExpedienteFila,
    RevisionEntrada,
    RevisionResultado,
    RevisionSalida,
)
from app.seguridad.dependencias import UsuarioActual, contexto_peticion, requiere_rol
from app.servicios.logistica.cuadro import ServicioCuadro
from app.servicios.logistica.expedientes import listar_expedientes
from app.servicios.logistica.proveedores import ServicioProveedores, salida
from app.servicios.logistica.revision import ServicioRevision
from app.servicios.seguridad.bitacora import Contexto

router = APIRouter(tags=["logística y certificación"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]
ContextoDep = Annotated[Contexto, Depends(contexto_peticion)]
Logistica = Annotated[UsuarioActual, Depends(requiere_rol("JL"))]
LogisticaOPresupuesto = Annotated[UsuarioActual, Depends(requiere_rol("JL", "JP"))]


@router.get("/expedientes", response_model=list[ExpedienteFila])
def expedientes(
    usuario: LogisticaOPresupuesto, sesion: SesionDep, reloj: RelojDep,
    estado: Annotated[str, Query(max_length=30)],
) -> list[ExpedienteFila]:
    """Expedientes en un estado que trabaja el rol: Aprobado, Documentación validada y
    Certificado para Logística; Cuadro comparativo registrado para Presupuesto."""
    return listar_expedientes(sesion, usuario.codigo_rol, estado, reloj())


@router.get("/requerimientos/{id_requerimiento}/revision", response_model=RevisionSalida)
def consultar_revision(id_requerimiento: int, usuario: Logistica, sesion: SesionDep,
                       reloj: RelojDep, contexto: ContextoDep) -> RevisionSalida:
    """Documentos del expediente con su última revisión (P09)."""
    return ServicioRevision(sesion, reloj, contexto).consultar(id_requerimiento, usuario)


@router.post("/requerimientos/{id_requerimiento}/revision", response_model=RevisionResultado)
def registrar_revision(id_requerimiento: int, datos: RevisionEntrada, usuario: Logistica,
                       sesion: SesionDep, reloj: RelojDep,
                       contexto: ContextoDep) -> RevisionResultado:
    """Registra la validación documental: conforme o devuelta al Área Usuaria (CU-07)."""
    return ServicioRevision(sesion, reloj, contexto).registrar(id_requerimiento, datos, usuario)


@router.get("/proveedores", response_model=BusquedaProveedor)
def buscar_proveedor(_: Logistica, sesion: SesionDep,
                     ruc: Annotated[str, Query(pattern=r"^\d{11}$")]) -> BusquedaProveedor:
    """Busca un proveedor por RUC sin descifrar los datos guardados (ruc_hash)."""
    proveedor = ServicioProveedores(sesion).buscar(ruc)
    return BusquedaProveedor(encontrado=proveedor is not None,
                             proveedor=salida(proveedor) if proveedor else None)


@router.get("/requerimientos/{id_requerimiento}/cuadro", response_model=CuadroSalida)
def consultar_cuadro(id_requerimiento: int, usuario: LogisticaOPresupuesto, sesion: SesionDep,
                     reloj: RelojDep, contexto: ContextoDep) -> CuadroSalida:
    """Cuadro comparativo del requerimiento (P10; para Presupuesto, sin datos del proveedor)."""
    return ServicioCuadro(sesion, reloj, contexto).consultar(id_requerimiento, usuario)


@router.put("/requerimientos/{id_requerimiento}/cuadro", response_model=CuadroResultado)
def guardar_cuadro(id_requerimiento: int, datos: CuadroEntrada, usuario: Logistica,
                   sesion: SesionDep, reloj: RelojDep, contexto: ContextoDep) -> CuadroResultado:
    """Registra o corrige el único cuadro del requerimiento y revalida con el precio de
    mercado (CU-08, RF-12)."""
    return ServicioCuadro(sesion, reloj, contexto).guardar(id_requerimiento, datos, usuario)
