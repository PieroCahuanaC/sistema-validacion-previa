"""DTO de autenticación y de gestión de usuarios (CU-09, CU-15)."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NombreUsuario = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True,
                                                 min_length=3, max_length=30,
                                                 pattern=r"^[a-z0-9._-]+$")]


class IngresoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_usuario: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True,
                                                     min_length=1, max_length=30)]
    contrasena: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class CambioContrasenaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contrasena_actual: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    contrasena_nueva: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class RolSalida(BaseModel):
    codigo: str
    nombre: str


class UnidadSalida(BaseModel):
    sigla: str | None
    nombre: str


class UsuarioSesionSalida(BaseModel):
    """Datos del usuario autenticado para la barra superior y el menú (P02)."""

    id_usuario: int
    nombre_usuario: str
    nombres_apellidos: str
    rol: RolSalida
    unidad: UnidadSalida | None
    contrasena_temporal: bool
    reglas_contrasena: list[str]


class UsuarioEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_usuario: NombreUsuario
    nombres_apellidos: Annotated[Texto, StringConstraints(max_length=120)]
    codigo_rol: Literal["AU", "GA", "JL", "JP", "ADM"]
    unidad_sigla: Annotated[str, StringConstraints(max_length=15)] | None = None


class UsuarioModificacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombres_apellidos: Annotated[Texto, StringConstraints(max_length=120)]
    codigo_rol: Literal["AU", "GA", "JL", "JP", "ADM"]
    unidad_sigla: Annotated[str, StringConstraints(max_length=15)] | None = None


class UsuarioSalida(BaseModel):
    """Fila de la P16. Nunca incluye el hash de la contraseña."""

    id_usuario: int
    nombre_usuario: str
    nombres_apellidos: str
    rol: RolSalida
    unidad: UnidadSalida | None
    estado: str
    contrasena_temporal: bool
    bloqueado: bool


class ContrasenaTemporalSalida(BaseModel):
    """La contraseña temporal se muestra una sola vez al Administrador y no se guarda."""

    usuario: UsuarioSalida
    contrasena_temporal: str


class CatalogosUsuarioSalida(BaseModel):
    roles: list[RolSalida]
    unidades: list[UnidadSalida]
