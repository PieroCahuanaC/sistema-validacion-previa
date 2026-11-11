"""Endpoints de gestión de usuarios (P16, CU-15, RF-15). Solo el Administrador del sistema."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import obtener_sesion
from app.core.reloj import Reloj, obtener_reloj
from app.esquemas.seguridad import (
    CatalogosUsuarioSalida,
    ContrasenaTemporalSalida,
    UsuarioEntrada,
    UsuarioModificacion,
    UsuarioSalida,
)
from app.seguridad.dependencias import UsuarioActual, contexto_peticion, requiere_rol
from app.servicios.seguridad.bitacora import Contexto
from app.servicios.seguridad.usuarios import ServicioUsuarios

router = APIRouter(prefix="/usuarios", tags=["gestión de usuarios"])

Administrador = Annotated[UsuarioActual, Depends(requiere_rol("ADM"))]
SesionDep = Annotated[Session, Depends(obtener_sesion)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]
ContextoDep = Annotated[Contexto, Depends(contexto_peticion)]


def _servicio(sesion: Session, reloj: Reloj, contexto: Contexto,
              admin: UsuarioActual) -> ServicioUsuarios:
    return ServicioUsuarios(sesion, reloj, contexto, admin)


@router.get("/catalogos", response_model=CatalogosUsuarioSalida)
def catalogos(admin: Administrador, sesion: SesionDep, reloj: RelojDep,
              contexto: ContextoDep) -> CatalogosUsuarioSalida:
    """Roles y unidades orgánicas activas para el formulario de la P16."""
    return _servicio(sesion, reloj, contexto, admin).catalogos()


@router.get("", response_model=list[UsuarioSalida])
def listar(
    admin: Administrador, sesion: SesionDep, reloj: RelojDep, contexto: ContextoDep,
    rol: Annotated[str | None, Query(max_length=5)] = None,
    unidad: Annotated[str | None, Query(max_length=15)] = None,
    estado: Literal["ACTIVO", "BAJA"] | None = None,
    buscar: Annotated[str | None, Query(max_length=60)] = None,
) -> list[UsuarioSalida]:
    return _servicio(sesion, reloj, contexto, admin).listar(rol, unidad, estado, buscar)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ContrasenaTemporalSalida)
def crear(datos: UsuarioEntrada, admin: Administrador, sesion: SesionDep, reloj: RelojDep,
          contexto: ContextoDep) -> ContrasenaTemporalSalida:
    """Crea la cuenta con una contraseña temporal que se muestra una sola vez."""
    return _servicio(sesion, reloj, contexto, admin).crear(datos)


@router.put("/{id_usuario}", response_model=UsuarioSalida)
def modificar(id_usuario: int, datos: UsuarioModificacion, admin: Administrador,
              sesion: SesionDep, reloj: RelojDep, contexto: ContextoDep) -> UsuarioSalida:
    return _servicio(sesion, reloj, contexto, admin).modificar(id_usuario, datos)


@router.post("/{id_usuario}/restablecimiento", response_model=ContrasenaTemporalSalida)
def restablecer(id_usuario: int, admin: Administrador, sesion: SesionDep, reloj: RelojDep,
                contexto: ContextoDep) -> ContrasenaTemporalSalida:
    """Genera una contraseña temporal, desbloquea la cuenta y cierra sus sesiones."""
    return _servicio(sesion, reloj, contexto, admin).restablecer(id_usuario)


@router.post("/{id_usuario}/baja", response_model=UsuarioSalida)
def dar_de_baja(id_usuario: int, admin: Administrador, sesion: SesionDep, reloj: RelojDep,
                contexto: ContextoDep) -> UsuarioSalida:
    """Baja lógica e irreversible: seudonimiza la cuenta y cierra sus sesiones."""
    return _servicio(sesion, reloj, contexto, admin).dar_de_baja(id_usuario)
