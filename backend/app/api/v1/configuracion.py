"""Endpoints de configuración del Jefe de Presupuesto: reglas del semáforo (P14; CU-12,
RNF-04) y base presupuestal con carga CSV de respaldo (P15; RF-14, riesgo R01).

Solo el Jefe de Presupuesto puede invocarlos (rol por endpoint, Práctica 5).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import obtener_sesion
from app.core.reloj import Reloj, obtener_reloj
from app.esquemas.configuracion import (
    BasePresupuestalSalida,
    CargaEntrada,
    ParametrosSemaforo,
    ReglasSalida,
    ResultadoCarga,
    ValidacionCargaSalida,
)
from app.seguridad.dependencias import UsuarioActual, contexto_peticion, requiere_rol
from app.servicios.configuracion.reglas import ServicioReglas
from app.servicios.presupuesto.base import ServicioBasePresupuestal
from app.servicios.seguridad.bitacora import Contexto

router = APIRouter(tags=["configuración de Presupuesto"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]
ContextoDep = Annotated[Contexto, Depends(contexto_peticion)]
Presupuesto = Annotated[UsuarioActual, Depends(requiere_rol("JP"))]


@router.get("/reglas", response_model=ReglasSalida)
def consultar_reglas(_: Presupuesto, sesion: SesionDep, reloj: RelojDep) -> ReglasSalida:
    """Versión vigente de la regla del semáforo y su historial de versiones (P14)."""
    return ServicioReglas(sesion, reloj).consultar()


@router.post("/reglas", response_model=ReglasSalida, status_code=status.HTTP_201_CREATED)
def guardar_regla(datos: ParametrosSemaforo, usuario: Presupuesto, sesion: SesionDep,
                  reloj: RelojDep, contexto: ContextoDep) -> ReglasSalida:
    """Crea una versión nueva de la regla y cierra la vigente (CU-12; bitácora CONFIG_REGLA).

    Las validaciones ya registradas conservan la versión con que se calcularon (R14).
    """
    return ServicioReglas(sesion, reloj, contexto).guardar_version(datos, usuario)


@router.get("/base-presupuestal", response_model=BasePresupuestalSalida)
def estado_base(_: Presupuesto, sesion: SesionDep, reloj: RelojDep) -> BasePresupuestalSalida:
    """Última ejecución, fecha de corte y resultado por fuente, con el historial (P15)."""
    return ServicioBasePresupuestal(sesion, reloj).estado()


@router.post("/base-presupuestal/validacion", response_model=ValidacionCargaSalida)
def validar_archivo(datos: CargaEntrada, _: Presupuesto, sesion: SesionDep,
                    reloj: RelojDep) -> ValidacionCargaSalida:
    """Valida el CSV y devuelve la vista previa con los errores por fila; no escribe nada."""
    return ServicioBasePresupuestal(sesion, reloj).validar(datos)


@router.post("/base-presupuestal/cargas", response_model=ResultadoCarga,
             status_code=status.HTTP_201_CREATED)
def cargar_archivo(datos: CargaEntrada, usuario: Presupuesto, sesion: SesionDep,
                   reloj: RelojDep, contexto: ContextoDep) -> ResultadoCarga:
    """Vuelve a validar el CSV completo y, si no tiene errores, lo carga (origen MANUAL_CSV).

    Si tiene errores, la carga queda registrada como RECHAZADA y responde 422.
    """
    return ServicioBasePresupuestal(sesion, reloj, contexto).cargar(datos, usuario)
