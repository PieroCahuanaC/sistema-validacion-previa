"""Proveedores del cuadro comparativo (P10).

Se buscan por RUC sin descifrar (ruc_hash, HMAC). El RUC y el nombre de una persona natural
son datos personales y se guardan cifrados; los de una persona jurídica, no (Ley N.° 29733).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import DatosNoValidos, ErrorNegocio
from app.esquemas.logistica import ProveedorNuevo, ProveedorSalida
from app.modelos.logistica import Proveedor
from app.seguridad import cifrado

PREFIJOS = {"NATURAL": ("10", "15", "17"), "JURIDICA": ("20",)}


def verificar_ruc(ruc: str, tipo_persona: str | None = None) -> None:
    if not cifrado.ruc_valido(ruc):
        raise DatosNoValidos("El RUC no es válido: debe tener 11 dígitos y un dígito "
                             "verificador correcto.")
    if tipo_persona and not ruc.startswith(PREFIJOS[tipo_persona]):
        esperado = "10, 15 o 17" if tipo_persona == "NATURAL" else "20"
        raise DatosNoValidos(f"El RUC de una persona {tipo_persona.lower()} empieza con "
                             f"{esperado}.")


def salida(proveedor: Proveedor) -> ProveedorSalida:
    return ProveedorSalida(id_proveedor=proveedor.id_proveedor,
                           tipo_persona=proveedor.tipo_persona,
                           ruc=cifrado.descifrar(proveedor.ruc),
                           razon_social=cifrado.descifrar(proveedor.razon_social))


class ServicioProveedores:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def buscar(self, ruc: str) -> Proveedor | None:
        verificar_ruc(ruc)
        return self._sesion.scalar(select(Proveedor).where(
            Proveedor.ruc_hash == cifrado.resumen_ruc(ruc)))

    def obtener(self, id_proveedor: int) -> Proveedor:
        proveedor = self._sesion.get(Proveedor, id_proveedor)
        if proveedor is None:
            raise DatosNoValidos(f"El proveedor {id_proveedor} no existe.")
        return proveedor

    def obtener_o_registrar(self, datos: ProveedorNuevo) -> Proveedor:
        verificar_ruc(datos.ruc, datos.tipo_persona)
        existente = self.buscar(datos.ruc)
        if existente is not None:
            if existente.tipo_persona != datos.tipo_persona:
                raise ErrorNegocio(409, "Conflicto", "El RUC ya está registrado con otro tipo "
                                   "de persona.")
            return existente
        natural = datos.tipo_persona == "NATURAL"
        proveedor = Proveedor(
            tipo_persona=datos.tipo_persona, ruc_hash=cifrado.resumen_ruc(datos.ruc),
            ruc=cifrado.cifrar(datos.ruc) if natural else datos.ruc,
            razon_social=cifrado.cifrar(datos.razon_social) if natural else datos.razon_social)
        self._sesion.add(proveedor)
        self._sesion.flush()
        return proveedor
