"""Endpoint de la pantalla Inicio (P02), para todos los roles autenticados."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import obtener_sesion
from app.core.reloj import Reloj, obtener_reloj
from app.esquemas.inicio import InicioSalida
from app.seguridad.dependencias import UsuarioActual, usuario_actual
from app.servicios.validacion.inicio import construir_inicio

router = APIRouter(tags=["inicio"])


@router.get("/inicio", response_model=InicioSalida)
def inicio(
    usuario: Annotated[UsuarioActual, Depends(usuario_actual)],
    sesion: Annotated[Session, Depends(obtener_sesion)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> InicioSalida:
    """Fecha de corte de los datos y, para el Área Usuaria, su resumen y sus pendientes."""
    return construir_inicio(sesion, usuario, reloj())
