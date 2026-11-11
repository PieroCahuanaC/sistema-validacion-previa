"""Cuadro comparativo del análisis de mercado (CU-08, RF-12; pantalla P10).

- Exige al menos una cotización; un proveedor cotiza una sola vez en el cuadro (UNIQUE).
- Cada requerimiento admite un solo cuadro (R26): si Presupuesto lo devuelve, o si el
  requerimiento vuelve a Logística tras un ajuste, el mismo cuadro se corrige y en la bitácora
  queda el valor anterior y el nuevo (cambio 4 de la Tabla 26 de la Práctica 7).
- Revalidación con el precio de mercado (cambio 8): si el precio de referencia supera el monto
  validado, se vuelve a calcular el semáforo con ese precio. En verde (o ámbar, que decide
  Presupuesto en la P11) el expediente pasa a Presupuesto; en rojo vuelve al Área Usuaria para
  ajustarlo en la P05, porque el requerimiento estaba subvaluado.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import DatosNoValidos, ErrorNegocio
from app.core.reloj import Reloj, fecha_local
from app.esquemas.logistica import (
    CotizacionSalida,
    CuadroEntrada,
    CuadroResultado,
    CuadroSalida,
)
from app.modelos.catalogos import Estado, Rol
from app.modelos.logistica import Cotizacion, CuadroComparativo
from app.modelos.requerimiento import HistorialEtapa, Requerimiento
from app.seguridad.dependencias import UsuarioActual
from app.servicios.logistica.proveedores import ServicioProveedores, salida
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto
from app.servicios.trazabilidad.maquina import MaquinaEstados
from app.servicios.validacion.regla_semaforo import Semaforo
from app.servicios.validacion.servicio import ServicioValidacion
from app.servicios.validacion.situacion import situacion

CENTIMO = Decimal("0.01")


def cuadro_de(sesion: Session, id_requerimiento: int) -> CuadroComparativo | None:
    return sesion.scalar(select(CuadroComparativo)
                         .where(CuadroComparativo.id_requerimiento == id_requerimiento))


def devolucion_de_presupuesto(sesion: Session, requerimiento: Requerimiento) -> str | None:
    """Observación de Presupuesto si el último paso fue su devolución a Logística."""
    ultimo = sesion.scalar(
        select(HistorialEtapa).where(
            HistorialEtapa.id_requerimiento == requerimiento.id_requerimiento)
        .order_by(HistorialEtapa.fecha_hora.desc(), HistorialEtapa.id_historial.desc())
        .limit(1))
    if ultimo is None:
        return None
    estado = sesion.get(Estado, ultimo.id_estado)
    rol = sesion.get(Rol, ultimo.id_rol)
    if estado.codigo == "DOCUMENTACION_VALIDADA" and rol.codigo == "JP":
        return ultimo.observacion
    return None


class ServicioCuadro:
    def __init__(self, sesion: Session, reloj: Reloj, contexto: Contexto) -> None:
        self._sesion = sesion
        self._reloj = reloj
        self._contexto = contexto
        self._maquina = MaquinaEstados(sesion, reloj, contexto)
        self._proveedores = ServicioProveedores(sesion)

    def consultar(self, id_requerimiento: int, usuario: UsuarioActual) -> CuadroSalida:
        requerimiento = self._maquina.obtener(id_requerimiento, usuario)
        actual = situacion(self._sesion, requerimiento)
        cuadro = cuadro_de(self._sesion, id_requerimiento)
        logistica = usuario.codigo_rol == "JL"
        modo = "CONSULTA"
        if logistica and actual.codigo_estado == "DOCUMENTACION_VALIDADA":
            modo = "CORRECCION" if cuadro else "REGISTRO"
        montos = [c.monto for c in cuadro.cotizaciones] if cuadro else []
        return CuadroSalida(
            requerimiento_id=id_requerimiento, existe=cuadro is not None, modo=modo,
            monto_validado=actual.validacion.monto_evaluado,
            precio_referencia=cuadro.precio_referencia if cuadro else None,
            observacion=cuadro.observacion if cuadro else None,
            fecha_registro=cuadro.fecha_registro if cuadro else None,
            menor_cotizacion=min(montos) if montos else None,
            promedio=(sum(montos) / len(montos)).quantize(CENTIMO, ROUND_HALF_UP)
            if montos else None,
            cotizaciones=[CotizacionSalida(
                id_cotizacion=c.id_cotizacion, monto=c.monto,
                fecha_cotizacion=c.fecha_cotizacion,
                # Presupuesto no ve el RUC ni el nombre del proveedor (datos personales).
                proveedor=salida(self._proveedores.obtener(c.id_proveedor)) if logistica
                else None) for c in (cuadro.cotizaciones if cuadro else [])],
            devolucion_presupuesto=devolucion_de_presupuesto(self._sesion, requerimiento))

    def guardar(self, id_requerimiento: int, datos: CuadroEntrada,
                usuario: UsuarioActual) -> CuadroResultado:
        requerimiento = self._maquina.bloquear(id_requerimiento, usuario)
        actual = situacion(self._sesion, requerimiento)
        if actual.codigo_estado != "DOCUMENTACION_VALIDADA":
            raise ErrorNegocio(409, "Conflicto", "El cuadro comparativo se registra cuando la "
                               "documentación del expediente está validada.")
        # Verifica desde ya que el rol puede registrar el cuadro (403 si no).
        self._maquina.verificar(requerimiento, "CUADRO_REGISTRADO", usuario)
        momento = self._reloj()
        cotizaciones = self._cotizaciones(datos, fecha_local(momento))

        cuadro = cuadro_de(self._sesion, id_requerimiento)
        modo = "CORRECCION" if cuadro else "REGISTRO"
        anterior = None
        if cuadro is None:
            cuadro = CuadroComparativo(id_requerimiento=id_requerimiento, fecha_registro=momento,
                                       precio_referencia=datos.precio_referencia)
            self._sesion.add(cuadro)
        else:
            anterior = {"precio_referencia": str(cuadro.precio_referencia),
                        "cotizaciones": [{"id_proveedor": c.id_proveedor, "monto": str(c.monto)}
                                         for c in cuadro.cotizaciones]}
            cuadro.cotizaciones.clear()
            self._sesion.flush()  # retira las cotizaciones anteriores antes de insertar
            cuadro.fecha_registro = momento
        cuadro.precio_referencia = datos.precio_referencia
        cuadro.observacion = (datos.observacion or "").strip() or None
        cuadro.cotizaciones.extend(cotizaciones)
        self._sesion.flush()
        bitacora.registrar(
            self._sesion, momento, self._contexto, "REGISTRO_CUADRO", "EXITO",
            id_usuario=usuario.id_usuario, id_rol=usuario.id_rol,
            recurso_tipo="REQUERIMIENTO", recurso_id=id_requerimiento,
            detalle={"modo": modo, "precio_referencia": str(datos.precio_referencia),
                     "cotizaciones": [{"id_proveedor": c.id_proveedor, "monto": str(c.monto)}
                                      for c in cotizaciones],
                     "anterior": anterior})

        resultado = None
        if datos.precio_referencia > actual.validacion.monto_evaluado:
            resultado = ServicioValidacion(self._sesion, self._reloj, self._contexto).revalidar(
                requerimiento, usuario, momento, monto=datos.precio_referencia)
        if resultado is not None and resultado.estado == Semaforo.ROJO:
            destino, a_quien = "REGISTRADO", "AREA_USUARIA"
            precio = f"S/ {datos.precio_referencia:,.2f}"
            observacion = (f"El precio de referencia del mercado ({precio}) no tiene saldo "
                           "presupuestal suficiente. El Área Usuaria debe ajustar el "
                           "requerimiento.")
        else:
            destino, a_quien = "CUADRO_REGISTRADO", "PRESUPUESTO"
            observacion = (f"Precio de referencia S/ {datos.precio_referencia:,.2f}"
                           + (" (corrección del cuadro)" if modo == "CORRECCION" else ""))
        transicion = self._maquina.verificar(requerimiento, destino, usuario)
        self._maquina.registrar(requerimiento, transicion, destino, observacion, usuario, momento)
        self._sesion.commit()
        nueva = situacion(self._sesion, requerimiento)
        return CuadroResultado(
            requerimiento_id=id_requerimiento, codigo=requerimiento.codigo, modo=modo,
            revalidado=resultado is not None,
            estado_semaforo=str(resultado.estado) if resultado else None,
            semaforo_vigente=str(nueva.vigente), estado_actual=nueva.estado.nombre,
            destino=a_quien)

    def _cotizaciones(self, datos: CuadroEntrada, hoy: date) -> list[Cotizacion]:
        cotizaciones, vistos = [], set()
        for numero, entrada in enumerate(datos.cotizaciones, start=1):
            if (entrada.id_proveedor is None) == (entrada.proveedor is None):
                raise DatosNoValidos(f"Cotización {numero}: indique un proveedor registrado o "
                                     "los datos de uno nuevo.")
            if entrada.fecha_cotizacion > hoy:
                raise DatosNoValidos(f"Cotización {numero}: la fecha no puede ser futura.")
            proveedor = (self._proveedores.obtener(entrada.id_proveedor)
                         if entrada.id_proveedor is not None
                         else self._proveedores.obtener_o_registrar(entrada.proveedor))
            if proveedor.id_proveedor in vistos:
                raise DatosNoValidos("Un proveedor solo puede cotizar una vez en el mismo cuadro.")
            vistos.add(proveedor.id_proveedor)
            cotizaciones.append(Cotizacion(id_proveedor=proveedor.id_proveedor,
                                           monto=entrada.monto,
                                           fecha_cotizacion=entrada.fecha_cotizacion))
        return cotizaciones

