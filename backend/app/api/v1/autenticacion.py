"""Endpoints de autenticación (CU-09, RF-10; Tabla 13 de la Práctica 5).

Los tokens viajan solo en cookies HttpOnly, Secure y SameSite=Strict. El frontend las recibe
en su propio dominio porque Vercel reenvía /api/* a la API (mismo sitio), de modo que nunca
se guardan en el almacenamiento del navegador.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import obtener_configuracion
from app.core.db import obtener_sesion
from app.core.reloj import Reloj, obtener_reloj
from app.esquemas.seguridad import CambioContrasenaEntrada, IngresoEntrada, UsuarioSesionSalida
from app.modelos.seguridad import Usuario
from app.seguridad import tokens
from app.seguridad.dependencias import UsuarioActual, contexto_peticion, usuario_sesion
from app.servicios.seguridad.autenticacion import ServicioAutenticacion, SesionEmitida
from app.servicios.seguridad.bitacora import Contexto
from app.servicios.seguridad.usuarios import datos_de_sesion

router = APIRouter(prefix="/auth", tags=["autenticación"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]
ContextoDep = Annotated[Contexto, Depends(contexto_peticion)]
RUTA_RENOVACION = "/api/v1/auth"


def _poner_cookies(respuesta: Response, emitida: SesionEmitida) -> None:
    seguras = obtener_configuracion().cookie_segura
    respuesta.set_cookie(tokens.COOKIE_ACCESO, emitida.token_acceso, path="/api",
                         max_age=int(tokens.DURACION_ACCESO.total_seconds()),
                         httponly=True, secure=seguras, samesite="strict")
    respuesta.set_cookie(tokens.COOKIE_RENOVACION, emitida.token_renovacion,
                         path=RUTA_RENOVACION, max_age=emitida.segundos_renovacion,
                         httponly=True, secure=seguras, samesite="strict")


def _borrar_cookies(respuesta: Response) -> None:
    seguras = obtener_configuracion().cookie_segura
    respuesta.delete_cookie(tokens.COOKIE_ACCESO, path="/api", httponly=True, secure=seguras,
                            samesite="strict")
    respuesta.delete_cookie(tokens.COOKIE_RENOVACION, path=RUTA_RENOVACION, httponly=True,
                            secure=seguras, samesite="strict")


@router.post("/ingreso", response_model=UsuarioSesionSalida)
def ingresar(
    datos: IngresoEntrada, respuesta: Response, sesion: SesionDep, reloj: RelojDep,
    contexto: ContextoDep,
) -> UsuarioSesionSalida:
    """Inicia sesión (P01). 401 con intentos restantes; 423 si la cuenta queda bloqueada."""
    emitida = ServicioAutenticacion(sesion, reloj, contexto).ingresar(datos.nombre_usuario,
                                                                      datos.contrasena)
    _poner_cookies(respuesta, emitida)
    return datos_de_sesion(sesion, emitida.usuario)


@router.post("/renovacion", status_code=204)
def renovar(
    request: Request, respuesta: Response, sesion: SesionDep, reloj: RelojDep,
    contexto: ContextoDep,
) -> None:
    """Rota el token de renovación y emite un nuevo token de acceso."""
    emitida = ServicioAutenticacion(sesion, reloj, contexto).renovar(
        request.cookies.get(tokens.COOKIE_RENOVACION))
    _poner_cookies(respuesta, emitida)


@router.post("/salida", status_code=204)
def salir(
    request: Request, respuesta: Response, sesion: SesionDep, reloj: RelojDep,
    contexto: ContextoDep,
) -> None:
    """Cierra la sesión: revoca el token de renovación y borra las cookies."""
    acceso = request.cookies.get(tokens.COOKIE_ACCESO)
    carga = tokens.leer_acceso(acceso, reloj()) if acceso else None
    ServicioAutenticacion(sesion, reloj, contexto).salir(
        request.cookies.get(tokens.COOKIE_RENOVACION), int(carga["sid"]) if carga else None)
    _borrar_cookies(respuesta)


@router.post("/cambio-contrasena", status_code=204)
def cambiar_contrasena(
    datos: CambioContrasenaEntrada, usuario: Annotated[UsuarioActual, Depends(usuario_sesion)],
    sesion: SesionDep, reloj: RelojDep, contexto: ContextoDep,
) -> None:
    """Cambia la contraseña; obligatorio en el primer ingreso con contraseña temporal."""
    ServicioAutenticacion(sesion, reloj, contexto).cambiar_contrasena(
        usuario.id_usuario, datos.contrasena_actual, datos.contrasena_nueva)


@router.get("/yo", response_model=UsuarioSesionSalida)
def yo(
    usuario: Annotated[UsuarioActual, Depends(usuario_sesion)], sesion: SesionDep
) -> UsuarioSesionSalida:
    """Usuario de la sesión actual: nombre, rol, unidad y si debe cambiar su contraseña."""
    return datos_de_sesion(sesion, sesion.get(Usuario, usuario.id_usuario))
