"""Autenticación: ingreso, renovación, cierre de sesión y cambio de contraseña (CU-09, RF-10).

Implementa las decisiones de la Tabla 13 de la Práctica 5: Argon2id, bloqueo temporal de 15
minutos tras tres intentos fallidos, contraseña temporal de cambio obligatorio, token de
acceso de 15 minutos y token de renovación de hasta 8 horas que se rota en cada uso.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errores import DatosNoValidos, ErrorNegocio
from app.core.reloj import Reloj
from app.modelos.catalogos import Rol
from app.modelos.seguridad import SesionUsuario, Usuario
from app.seguridad import contrasenas, tokens
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto

MAXIMO_INTENTOS = 3
DURACION_BLOQUEO = timedelta(minutes=15)
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos."


@dataclass(frozen=True)
class SesionEmitida:
    usuario: Usuario
    codigo_rol: str
    id_sesion: int
    token_acceso: str
    token_renovacion: str
    expira_renovacion: datetime
    emitida_en: datetime

    @property
    def segundos_renovacion(self) -> int:
        """Vida restante del token de renovación (la rotación no extiende las 8 horas)."""
        return max(0, int((self.expira_renovacion - self.emitida_en).total_seconds()))


class ServicioAutenticacion:
    def __init__(self, sesion: Session, reloj: Reloj, contexto: Contexto) -> None:
        self._sesion = sesion
        self._reloj = reloj
        self._contexto = contexto

    # --- CU-09: iniciar sesión --------------------------------------------------------------
    def ingresar(self, nombre_usuario: str, contrasena: str) -> SesionEmitida:
        ahora = self._reloj()
        usuario = self._sesion.scalar(select(Usuario).where(
            Usuario.nombre_usuario == nombre_usuario, Usuario.estado == "ACTIVO"))
        if usuario is None:
            self._registrar("LOGIN_FALLIDO", "DENEGADO", None, {"motivo": "credenciales"})
            self._sesion.commit()
            raise ErrorNegocio(401, "No autorizado", MENSAJE_CREDENCIALES)

        if usuario.bloqueado_hasta is not None and usuario.bloqueado_hasta > ahora:
            self._registrar("LOGIN_FALLIDO", "DENEGADO", usuario, {"motivo": "cuenta_bloqueada"})
            self._sesion.commit()
            raise self._error_bloqueo(usuario.bloqueado_hasta)

        if not contrasenas.verificar(contrasena, usuario.hash_contrasena):
            raise self._intento_fallido(usuario, ahora)

        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        emitida = self._abrir_sesion(usuario, ahora, ahora + tokens.DURACION_RENOVACION)
        self._registrar("LOGIN_EXITOSO", "EXITO", usuario, None, "SESION", emitida.id_sesion)
        self._sesion.commit()
        return emitida

    def _intento_fallido(self, usuario: Usuario, ahora: datetime) -> ErrorNegocio:
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= MAXIMO_INTENTOS:
            usuario.intentos_fallidos = 0
            usuario.bloqueado_hasta = ahora + DURACION_BLOQUEO
            self._registrar("BLOQUEO_CUENTA", "DENEGADO", usuario,
                            {"bloqueado_hasta": usuario.bloqueado_hasta.isoformat()})
            self._sesion.commit()
            return self._error_bloqueo(usuario.bloqueado_hasta)
        restantes = MAXIMO_INTENTOS - usuario.intentos_fallidos
        self._registrar("LOGIN_FALLIDO", "DENEGADO", usuario, {"intentos_restantes": restantes})
        self._sesion.commit()
        return ErrorNegocio(401, "No autorizado", MENSAJE_CREDENCIALES,
                            {"intentos_restantes": restantes})

    @staticmethod
    def _error_bloqueo(hasta: datetime) -> ErrorNegocio:
        return ErrorNegocio(423, "Cuenta bloqueada",
                            "La cuenta está bloqueada temporalmente por intentos fallidos.",
                            {"bloqueado_hasta": hasta.isoformat()})

    # --- Renovación con rotación ------------------------------------------------------------
    def renovar(self, token_renovacion: str | None) -> SesionEmitida:
        ahora = self._reloj()
        fila = self._sesion.scalar(select(SesionUsuario).where(
            SesionUsuario.hash_token == tokens.resumen(token_renovacion or "")))
        if fila is None or fila.expira_en <= ahora:
            raise ErrorNegocio(401, "Sesión no válida", "Su sesión terminó. Inicie sesión.")
        usuario = self._sesion.get(Usuario, fila.id_usuario)
        if fila.revocada_en is not None:
            # Un token ya rotado que vuelve a usarse indica robo: se cierran todas sus sesiones.
            self.revocar_sesiones(fila.id_usuario, ahora)
            self._registrar("ACCESO_DENEGADO", "DENEGADO", usuario,
                            {"motivo": "reuso_token_renovacion"}, "SESION", fila.id_sesion)
            self._sesion.commit()
            raise ErrorNegocio(401, "Sesión no válida", "Su sesión terminó. Inicie sesión.")
        if usuario is None or usuario.estado != "ACTIVO":
            raise ErrorNegocio(401, "Sesión no válida", "Su sesión terminó. Inicie sesión.")
        fila.revocada_en = ahora
        emitida = self._abrir_sesion(usuario, ahora, fila.expira_en)
        self._sesion.commit()
        return emitida

    # --- Cierre de sesión -------------------------------------------------------------------
    def salir(self, token_renovacion: str | None, id_sesion: int | None) -> None:
        ahora = self._reloj()
        fila = None
        if token_renovacion:
            fila = self._sesion.scalar(select(SesionUsuario).where(
                SesionUsuario.hash_token == tokens.resumen(token_renovacion)))
        if fila is None and id_sesion is not None:
            fila = self._sesion.get(SesionUsuario, id_sesion)
        if fila is None or fila.revocada_en is not None:
            return
        fila.revocada_en = ahora
        self._registrar("CIERRE_SESION", "EXITO", self._sesion.get(Usuario, fila.id_usuario),
                        None, "SESION", fila.id_sesion)
        self._sesion.commit()

    # --- Cambio de contraseña ---------------------------------------------------------------
    def cambiar_contrasena(self, id_usuario: int, actual: str, nueva: str) -> None:
        usuario = self._sesion.get(Usuario, id_usuario)
        if usuario is None or not contrasenas.verificar(actual, usuario.hash_contrasena):
            raise DatosNoValidos("La contraseña actual no es correcta.")
        faltas = contrasenas.incumplimientos(nueva, usuario.nombre_usuario)
        if nueva == actual:
            faltas.append("Distinta de la contraseña actual")
        if faltas:
            raise ErrorNegocio(422, "Datos de entrada no válidos",
                               "La nueva contraseña no cumple las reglas.", {"reglas": faltas})
        usuario.hash_contrasena = contrasenas.hashear(nueva)
        usuario.contrasena_temporal = False
        self._registrar("CAMBIO_CONTRASENA", "EXITO", usuario, None, "USUARIO",
                        usuario.id_usuario)
        self._sesion.commit()

    # --- Apoyo --------------------------------------------------------------------------------
    def revocar_sesiones(self, id_usuario: int, ahora: datetime) -> None:
        """Revoca todas las sesiones vigentes del usuario (baja, restablecimiento, robo)."""
        self._sesion.execute(
            update(SesionUsuario)
            .where(SesionUsuario.id_usuario == id_usuario, SesionUsuario.revocada_en.is_(None))
            .values(revocada_en=ahora))

    def _abrir_sesion(self, usuario: Usuario, ahora: datetime, expira: datetime) -> SesionEmitida:
        token, hash_token = tokens.nuevo_token_renovacion()
        fila = SesionUsuario(id_usuario=usuario.id_usuario, hash_token=hash_token,
                             emitida_en=ahora, expira_en=expira)
        self._sesion.add(fila)
        self._sesion.flush()
        rol = self._sesion.get(Rol, usuario.id_rol)
        codigo_rol = rol.codigo if rol else ""
        return SesionEmitida(
            usuario=usuario, codigo_rol=codigo_rol, id_sesion=fila.id_sesion,
            token_acceso=tokens.emitir_acceso(usuario.id_usuario, codigo_rol, fila.id_sesion,
                                              ahora),
            token_renovacion=token, expira_renovacion=expira, emitida_en=ahora,
        )

    def _registrar(
        self, accion: str, resultado: str, usuario: Usuario | None, detalle: dict | None,
        recurso_tipo: str | None = None, recurso_id: int | None = None,
    ) -> None:
        bitacora.registrar(
            self._sesion, self._reloj(), self._contexto, accion, resultado,
            id_usuario=usuario.id_usuario if usuario else None,
            id_rol=usuario.id_rol if usuario else None,
            recurso_tipo=recurso_tipo, recurso_id=recurso_id, detalle=detalle,
        )
