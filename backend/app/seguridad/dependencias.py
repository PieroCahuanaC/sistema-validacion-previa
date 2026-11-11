"""Usuario autenticado y control de acceso por rol (RF-10, RNF-03; sección 3 de la P5).

Incremento 2: reemplaza al usuario provisional del incremento 1. Cada petición se autentica
con la cookie de acceso (JWT de 15 minutos, HttpOnly, Secure, SameSite=Strict) y se verifica,
además, que su sesión siga vigente en la base de datos, de modo que el cierre de sesión, la
baja de un usuario o el restablecimiento de su contraseña tienen efecto inmediato.
"""

import ipaddress
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import obtener_sesion
from app.core.errores import ErrorNegocio
from app.core.reloj import Reloj, obtener_reloj
from app.modelos.catalogos import Rol
from app.modelos.seguridad import SesionUsuario, Usuario
from app.seguridad import tokens
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto


@dataclass(frozen=True)
class UsuarioActual:
    id_usuario: int | None
    id_rol: int
    codigo_rol: str
    id_unidad: int | None
    id_sesion: int | None = None
    contrasena_temporal: bool = False


def _no_autenticado() -> ErrorNegocio:
    return ErrorNegocio(401, "Sesión no válida", "Inicie sesión para continuar.")


def usuario_sesion(
    request: Request,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> UsuarioActual:
    """Usuario con sesión vigente, aunque todavía tenga la contraseña temporal."""
    token = request.cookies.get(tokens.COOKIE_ACCESO)
    carga = tokens.leer_acceso(token, reloj()) if token else None
    if carga is None:
        raise _no_autenticado()
    fila = sesion.get(SesionUsuario, int(carga["sid"]))
    usuario = sesion.get(Usuario, int(carga["sub"]))
    if (fila is None or usuario is None or fila.revocada_en is not None
            or fila.id_usuario != usuario.id_usuario or usuario.estado != "ACTIVO"):
        raise _no_autenticado()
    rol = sesion.get(Rol, usuario.id_rol)
    if rol is None:
        raise _no_autenticado()
    return UsuarioActual(usuario.id_usuario, usuario.id_rol, rol.codigo, usuario.id_unidad,
                         fila.id_sesion, usuario.contrasena_temporal)


def usuario_actual(usuario: Annotated[UsuarioActual, Depends(usuario_sesion)]) -> UsuarioActual:
    """Usuario autenticado que ya cambió su contraseña temporal (CU-09, flujo 3a)."""
    if usuario.contrasena_temporal:
        raise ErrorNegocio(403, "Acceso denegado",
                           "Debe cambiar su contraseña temporal antes de continuar.")
    return usuario


def requiere_rol(*codigos: str):
    """Dependencia que rechaza con 403 a los roles no autorizados para el endpoint y deja
    constancia en la bitácora (sección 3 de la Práctica 5: «queda registrada»)."""

    def _verificar(
        usuario: Annotated[UsuarioActual, Depends(usuario_actual)], request: Request,
        sesion: Annotated[Session, Depends(obtener_sesion)],
        reloj: Annotated[Reloj, Depends(obtener_reloj)],
    ) -> UsuarioActual:
        if usuario.codigo_rol not in codigos:
            bitacora.registrar(
                sesion, reloj(), contexto_peticion(request), "ACCESO_DENEGADO", "DENEGADO",
                id_usuario=usuario.id_usuario, id_rol=usuario.id_rol,
                detalle={"metodo": request.method, "ruta": request.url.path})
            sesion.commit()
            raise ErrorNegocio(403, "Acceso denegado", "Su rol no está autorizado.")
        return usuario

    return _verificar


def contexto_peticion(request: Request) -> Contexto:
    """IP de origen (detrás del proxy de Vercel y de Render) para la bitácora."""
    reenviada = request.headers.get("x-forwarded-for", "")
    candidata = reenviada.split(",")[0].strip() or (request.client.host if request.client
                                                   else "")
    try:
        ip = str(ipaddress.ip_address(candidata))
    except ValueError:
        ip = None
    return Contexto(ip_origen=ip)
