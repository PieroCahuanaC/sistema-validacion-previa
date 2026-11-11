"""Gestión de usuarios y roles por el Administrador del sistema (CU-15, RF-15; pantalla P16).

- Solo el Administrador crea cuentas; no existe autorregistro (Tabla 13 de la Práctica 5).
- La contraseña inicial y la restablecida son temporales y se muestran una sola vez.
- La baja es lógica: se conserva el registro para la bitácora, se cierran sus sesiones y sus
  datos personales se reemplazan por un seudónimo (RI-06; Ley N.° 29733).
"""

import re
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errores import DatosNoValidos, ErrorNegocio, NoEncontrado
from app.core.reloj import Reloj
from app.esquemas.seguridad import (
    CatalogosUsuarioSalida,
    ContrasenaTemporalSalida,
    RolSalida,
    UnidadSalida,
    UsuarioEntrada,
    UsuarioModificacion,
    UsuarioSalida,
    UsuarioSesionSalida,
)
from app.modelos.catalogos import Rol, UnidadOrganica
from app.modelos.seguridad import Usuario
from app.seguridad import contrasenas
from app.seguridad.dependencias import UsuarioActual
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.autenticacion import ServicioAutenticacion
from app.servicios.seguridad.bitacora import Contexto

NOMBRE_DADO_DE_BAJA = "Usuario dado de baja"


def _rol_salida(rol: Rol) -> RolSalida:
    return RolSalida(codigo=rol.codigo, nombre=rol.nombre)


def _unidad_salida(unidad: UnidadOrganica | None) -> UnidadSalida | None:
    return UnidadSalida(sigla=unidad.sigla, nombre=unidad.nombre) if unidad else None


def datos_de_sesion(sesion: Session, usuario: Usuario) -> UsuarioSesionSalida:
    rol = sesion.get(Rol, usuario.id_rol)
    unidad = sesion.get(UnidadOrganica, usuario.id_unidad) if usuario.id_unidad else None
    return UsuarioSesionSalida(
        id_usuario=usuario.id_usuario, nombre_usuario=usuario.nombre_usuario,
        nombres_apellidos=usuario.nombres_apellidos, rol=_rol_salida(rol),
        unidad=_unidad_salida(unidad), contrasena_temporal=usuario.contrasena_temporal,
        reglas_contrasena=list(contrasenas.REGLAS),
    )


class ServicioUsuarios:
    def __init__(self, sesion: Session, reloj: Reloj, contexto: Contexto,
                 administrador: UsuarioActual) -> None:
        self._sesion = sesion
        self._reloj = reloj
        self._contexto = contexto
        self._admin = administrador

    # --- Consultas ----------------------------------------------------------------------------
    def catalogos(self) -> CatalogosUsuarioSalida:
        roles = self._sesion.scalars(select(Rol).order_by(Rol.id_rol))
        unidades = self._sesion.scalars(select(UnidadOrganica)
                                        .where(UnidadOrganica.activa.is_(True))
                                        .order_by(UnidadOrganica.nombre))
        return CatalogosUsuarioSalida(roles=[_rol_salida(r) for r in roles],
                                      unidades=[_unidad_salida(u) for u in unidades])

    def listar(self, codigo_rol: str | None, unidad_sigla: str | None, estado: str | None,
               buscar: str | None) -> list[UsuarioSalida]:
        consulta = select(Usuario).order_by(Usuario.estado, Usuario.nombre_usuario)
        if codigo_rol:
            consulta = consulta.join(Rol, Rol.id_rol == Usuario.id_rol).where(
                Rol.codigo == codigo_rol)
        if unidad_sigla:
            consulta = consulta.join(UnidadOrganica,
                                     UnidadOrganica.id_unidad == Usuario.id_unidad).where(
                UnidadOrganica.sigla == unidad_sigla)
        if estado:
            consulta = consulta.where(Usuario.estado == estado)
        if buscar:
            patron = f"%{buscar.strip().lower()}%"
            consulta = consulta.where(or_(Usuario.nombre_usuario.ilike(patron),
                                          Usuario.nombres_apellidos.ilike(patron)))
        return [self._salida(u) for u in self._sesion.scalars(consulta)]

    # --- Altas, cambios y bajas ---------------------------------------------------------------
    def crear(self, datos: UsuarioEntrada) -> ContrasenaTemporalSalida:
        if re.search(r"\d{8}", datos.nombre_usuario):
            raise DatosNoValidos("El nombre de usuario no debe construirse con el DNI.")
        rol, unidad = self._rol_y_unidad(datos.codigo_rol, datos.unidad_sigla)
        temporal = contrasenas.generar_temporal()
        usuario = Usuario(
            id_rol=rol.id_rol, id_unidad=unidad.id_unidad if unidad else None,
            nombre_usuario=datos.nombre_usuario, nombres_apellidos=datos.nombres_apellidos,
            hash_contrasena=contrasenas.hashear(temporal), contrasena_temporal=True,
            intentos_fallidos=0, estado="ACTIVO",
        )
        self._sesion.add(usuario)
        try:
            self._sesion.flush()
        except IntegrityError as error:
            self._sesion.rollback()
            raise ErrorNegocio(409, "Conflicto", "El nombre de usuario ya existe.") from error
        self._registrar("ALTA_USUARIO", usuario, {"rol": rol.codigo})
        self._sesion.commit()
        return ContrasenaTemporalSalida(usuario=self._salida(usuario),
                                        contrasena_temporal=temporal)

    def modificar(self, id_usuario: int, datos: UsuarioModificacion) -> UsuarioSalida:
        usuario = self._ajeno(id_usuario, "modificar su propia cuenta")
        rol, unidad = self._rol_y_unidad(datos.codigo_rol, datos.unidad_sigla)
        cambio_de_rol = usuario.id_rol != rol.id_rol or usuario.id_unidad != (
            unidad.id_unidad if unidad else None)
        anterior = {"rol": usuario.id_rol, "unidad": usuario.id_unidad}
        usuario.nombres_apellidos = datos.nombres_apellidos
        usuario.id_rol = rol.id_rol
        usuario.id_unidad = unidad.id_unidad if unidad else None
        if cambio_de_rol:  # el nuevo permiso rige desde el siguiente ingreso
            self._autenticacion().revocar_sesiones(usuario.id_usuario, self._reloj())
        self._registrar("MODIFICACION_USUARIO", usuario,
                        {"anterior": anterior, "nuevo": {"rol": rol.id_rol,
                                                         "unidad": usuario.id_unidad}})
        self._sesion.commit()
        return self._salida(usuario)

    def restablecer(self, id_usuario: int) -> ContrasenaTemporalSalida:
        usuario = self._ajeno(id_usuario, "restablecer su propia contraseña")
        temporal = contrasenas.generar_temporal()
        usuario.hash_contrasena = contrasenas.hashear(temporal)
        usuario.contrasena_temporal = True
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        self._autenticacion().revocar_sesiones(usuario.id_usuario, self._reloj())
        self._registrar("RESTABLECER_CONTRASENA", usuario, None)
        self._sesion.commit()
        return ContrasenaTemporalSalida(usuario=self._salida(usuario),
                                        contrasena_temporal=temporal)

    def dar_de_baja(self, id_usuario: int) -> UsuarioSalida:
        usuario = self._ajeno(id_usuario, "darse de baja a sí mismo")
        usuario.estado = "BAJA"
        usuario.nombre_usuario = f"baja-{usuario.id_usuario}"
        usuario.nombres_apellidos = NOMBRE_DADO_DE_BAJA
        usuario.hash_contrasena = contrasenas.hashear(contrasenas.generar_temporal())
        self._autenticacion().revocar_sesiones(usuario.id_usuario, self._reloj())
        self._registrar("BAJA_USUARIO", usuario, None)
        self._sesion.commit()
        return self._salida(usuario)

    # --- Apoyo --------------------------------------------------------------------------------
    def _ajeno(self, id_usuario: int, accion: str) -> Usuario:
        """Usuario activo distinto del Administrador que opera (separación de funciones, P5:
        el Administrador no puede modificar su propia cuenta ni asignarse otro rol)."""
        if id_usuario == self._admin.id_usuario:
            raise ErrorNegocio(409, "Conflicto", f"No puede {accion}.")
        return self._activo(id_usuario)

    def _activo(self, id_usuario: int) -> Usuario:
        usuario = self._sesion.get(Usuario, id_usuario)
        if usuario is None:
            raise NoEncontrado("El usuario no existe.")
        if usuario.estado != "ACTIVO":
            raise ErrorNegocio(409, "Conflicto", "El usuario está dado de baja.")
        return usuario

    def _rol_y_unidad(self, codigo_rol: str,
                      unidad_sigla: str | None) -> tuple[Rol, UnidadOrganica | None]:
        rol = self._sesion.scalar(select(Rol).where(Rol.codigo == codigo_rol))
        if rol is None:
            raise DatosNoValidos("El rol no existe.")
        unidad = None
        if unidad_sigla:
            unidad = self._sesion.scalar(select(UnidadOrganica).where(
                UnidadOrganica.sigla == unidad_sigla, UnidadOrganica.activa.is_(True)))
            if unidad is None:
                raise DatosNoValidos("La unidad orgánica no existe o no está activa.")
        if codigo_rol == "AU" and unidad is None:  # RI-13
            raise DatosNoValidos("La unidad orgánica es obligatoria para el Área Usuaria.")
        return rol, unidad

    def _salida(self, usuario: Usuario) -> UsuarioSalida:
        ahora: datetime = self._reloj()
        rol = self._sesion.get(Rol, usuario.id_rol)
        unidad = (self._sesion.get(UnidadOrganica, usuario.id_unidad)
                  if usuario.id_unidad else None)
        return UsuarioSalida(
            id_usuario=usuario.id_usuario, nombre_usuario=usuario.nombre_usuario,
            nombres_apellidos=usuario.nombres_apellidos, rol=_rol_salida(rol),
            unidad=_unidad_salida(unidad), estado=usuario.estado,
            contrasena_temporal=usuario.contrasena_temporal,
            bloqueado=usuario.bloqueado_hasta is not None and usuario.bloqueado_hasta > ahora,
        )

    def _autenticacion(self) -> ServicioAutenticacion:
        return ServicioAutenticacion(self._sesion, self._reloj, self._contexto)

    def _registrar(self, accion: str, usuario: Usuario, detalle: dict | None) -> None:
        bitacora.registrar(
            self._sesion, self._reloj(), self._contexto, accion, "EXITO",
            id_usuario=self._admin.id_usuario, id_rol=self._admin.id_rol,
            recurso_tipo="USUARIO", recurso_id=usuario.id_usuario, detalle=detalle,
        )
