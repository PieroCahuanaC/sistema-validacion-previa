"""Endpoint del tablero de visibilidad (P06; GET /tablero del contrato de la API, con los roles
ampliados por el cambio 2 de la Tabla 26 de la Práctica 7)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_sesion
from app.core.reloj import Reloj, obtener_reloj
from app.esquemas.tablero import Orden, TableroSalida
from app.seguridad.dependencias import UsuarioActual, requiere_rol
from app.servicios.tablero.tablero import FiltrosTablero, ServicioTablero

router = APIRouter(tags=["tablero de visibilidad"])

RolFuncional = Annotated[UsuarioActual, Depends(requiere_rol("AU", "GA", "JL", "JP"))]
ESTADOS = ("^(REGISTRADO|APROBADO|DOCUMENTACION_VALIDADA|CUADRO_REGISTRADO|CERTIFICADO|"
           "ORDEN_EMITIDA|OBSERVADO|ANULADO)$")


@router.get("/tablero", response_model=TableroSalida)
def tablero(
    usuario: RolFuncional,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    meta: Annotated[str | None, Query(max_length=10)] = None,
    semaforo: Annotated[str | None, Query(pattern="^(VERDE|AMBAR|ROJO)$")] = None,
    estado: Annotated[str | None, Query(pattern=ESTADOS)] = None,
    buscar: Annotated[str | None, Query(max_length=15)] = None,
    cuello_de_botella: bool = False,
    orden: Orden = "meta",
    descendente: bool = False,
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
) -> TableroSalida:
    """Requerimientos con semáforo, estado, tiempo en la etapa y cuellos de botella (CU-02).

    El Área Usuaria ve solo los de su unidad; los demás roles funcionales, todos.
    """
    filtros = FiltrosTablero(meta=meta, semaforo=semaforo, estado=estado, buscar=buscar,
                             cuello_de_botella=cuello_de_botella, orden=orden,
                             descendente=descendente, pagina=pagina)
    return ServicioTablero(sesion).construir(usuario, filtros, reloj())
