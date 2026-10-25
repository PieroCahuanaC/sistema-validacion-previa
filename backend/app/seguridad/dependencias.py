"""Usuario actual y control de acceso por rol (RF-10, RNF-03).

INCREMENTO 1 — usuario provisional. La autenticación con Argon2id y la cookie de sesión
(RF-10, CU-09) corresponde al sprint del módulo de seguridad. Mientras tanto, la dependencia
usuario_actual entrega un usuario del Área Usuaria de la unidad configurada. Como los
endpoints ya la declaran por inyección de dependencias (sección 1.7 de la Práctica 5), al
implementar el RF-10 se reemplaza solo esta función, sin modificar ningún endpoint.
En el ambiente de producción la dependencia se niega a operar (falla cerrada).
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import obtener_configuracion
from app.core.db import obtener_sesion
from app.core.errores import ErrorNegocio
from app.repositorios.catalogos import RepositorioCatalogos


@dataclass(frozen=True)
class UsuarioActual:
    id_usuario: int | None
    id_rol: int
    codigo_rol: str
    id_unidad: int | None


def usuario_actual(sesion: Annotated[Session, Depends(obtener_sesion)]) -> UsuarioActual:
    config = obtener_configuracion()
    if config.ambiente == "produccion":
        raise ErrorNegocio(503, "Servicio no disponible",
                           "La autenticación aún no está habilitada en producción.")
    catalogos = RepositorioCatalogos(sesion)
    rol = catalogos.rol("AU")
    unidad = catalogos.unidad_por_sigla(config.usuario_provisional_unidad)
    if rol is None or unidad is None:
        raise ErrorNegocio(503, "Servicio no disponible",
                           "Faltan los catálogos iniciales: ejecute las semillas.")
    return UsuarioActual(id_usuario=None, id_rol=rol.id_rol, codigo_rol=rol.codigo,
                         id_unidad=unidad.id_unidad)


def requiere_rol(*codigos: str):
    """Dependencia que rechaza con 403 a los roles no autorizados para el endpoint."""

    def _verificar(usuario: Annotated[UsuarioActual, Depends(usuario_actual)]) -> UsuarioActual:
        if usuario.codigo_rol not in codigos:
            raise ErrorNegocio(403, "Acceso denegado", "Su rol no está autorizado.")
        return usuario

    return _verificar
