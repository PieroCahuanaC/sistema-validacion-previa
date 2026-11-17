"""P06. Tablero de visibilidad (CU-02; RF-06, RF-07 y RF-08; Tabla 7 de la Práctica 7).

Lista los requerimientos con su semáforo vigente, su estado y el tiempo que llevan en la
etapa, y resalta como cuello de botella los que superan el plazo de la directiva. El Área
Usuaria ve solo los de su unidad; la Gerencia, Logística y Presupuesto ven todos (cambio 2 de
la Tabla 26 de la Práctica 7). Incluye los trámites cerrados, que aparecen como tales.

El tablero se arma con un número fijo de consultas (situaciones_en_lote), y el filtro, el
orden y la paginación se aplican sobre ese resultado: con 200 a 250 requerimientos al mes, un
año completo cabe sin problema en memoria.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reloj import fecha_local
from app.esquemas.tablero import FilaTablero, MetaFiltro, TableroSalida, TarjetasTablero
from app.modelos.catalogos import UnidadOrganica
from app.modelos.presupuesto import MetaPresupuestal
from app.modelos.requerimiento import Requerimiento
from app.repositorios.catalogos import RepositorioCatalogos
from app.repositorios.presupuesto import RepositorioPresupuesto
from app.servicios.validacion.regla_semaforo import (
    ParametrosRegla,
    SaldoVigente,
    calcular_saldo_disponible,
)
from app.servicios.validacion.situacion import Situacion, situaciones_en_lote
from app.servicios.validacion.vigencia import SemaforoVigente

if TYPE_CHECKING:  # sin importar la conexión: las pruebas unitarias no usan BD
    from app.seguridad.dependencias import UsuarioActual


POR_PAGINA = 20
_SIN_SALDO = Decimal("Infinity")  # en el orden por meta, sin saldo va al final


@dataclass(frozen=True)
class FiltrosTablero:
    meta: str | None = None
    semaforo: str | None = None
    estado: str | None = None
    buscar: str | None = None
    cuello_de_botella: bool = False
    orden: str = "meta"
    descendente: bool = False
    pagina: int = 1


CLAVES_DE_ORDEN: dict[str, Callable[[FilaTablero], object]] = {
    # Orden por defecto de la P06: meta, saldo presupuestal disponible y fecha de necesidad.
    "meta": lambda f: (f.meta_codigo, f.saldo_disponible if f.saldo_disponible is not None
                       else _SIN_SALDO, f.fecha_necesidad),
    "codigo": lambda f: f.codigo,
    "objeto": lambda f: f.objeto_contratacion,
    "unidad": lambda f: f.unidad_sigla,
    "monto": lambda f: f.monto_estimado,
    "saldo": lambda f: f.saldo_disponible,
    "fecha_necesidad": lambda f: f.fecha_necesidad,
    "tiempo": lambda f: f.horas_en_etapa,
}


def _ordenar(filas: list[FilaTablero], orden: str, descendente: bool) -> list[FilaTablero]:
    clave = CLAVES_DE_ORDEN.get(orden, CLAVES_DE_ORDEN["meta"])
    con_valor = [f for f in filas if clave(f) is not None]
    sin_valor = [f for f in filas if clave(f) is None]  # siempre al final («—»)
    return sorted(con_valor, key=clave, reverse=descendente) + sin_valor


def _pasa_filtros(fila: FilaTablero, s: Situacion, f: FiltrosTablero) -> bool:
    if f.meta and fila.meta_codigo != f.meta:
        return False
    # Como en las tarjetas, los observados no se cuentan por color (P02 y P17).
    if f.semaforo and (s.codigo_estado == "OBSERVADO" or not s.vigente.startswith(f.semaforo)):
        return False
    if f.estado and s.codigo_estado != f.estado:
        return False
    if f.buscar and f.buscar.strip().upper() not in fila.codigo.upper():
        return False
    return not (f.cuello_de_botella and not fila.cuello_de_botella)


def _tarjetas(pares: list[tuple[FilaTablero, Situacion]]) -> TarjetasTablero:
    t = TarjetasTablero(en_tramite=0, verde=0, ambar=0, rojo=0, observado=0,
                        cuello_de_botella=0, cerrados=0)
    for fila, s in pares:
        if fila.cerrado:
            t.cerrados += 1
            continue
        t.en_tramite += 1
        if s.codigo_estado == "OBSERVADO":
            t.observado += 1
        elif s.vigente == SemaforoVigente.VERDE:
            t.verde += 1
        elif s.vigente == SemaforoVigente.ROJO:
            t.rojo += 1
        else:
            t.ambar += 1
        t.cuello_de_botella += fila.cuello_de_botella
    return t


class ServicioTablero:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion
        self._presupuesto = RepositorioPresupuesto(sesion)

    def construir(self, usuario: "UsuarioActual", filtros: FiltrosTablero,
                  ahora: datetime) -> TableroSalida:
        consulta = select(Requerimiento).order_by(Requerimiento.fecha_registro)
        unidad_texto = None
        if usuario.codigo_rol == "AU":  # filtro fijo por la unidad del usuario (Tabla 7)
            consulta = consulta.where(Requerimiento.id_unidad == usuario.id_unidad)
            unidad = self._sesion.get(UnidadOrganica, usuario.id_unidad)
            unidad_texto = f"{unidad.nombre} ({unidad.sigla})" if unidad else None
        situaciones = situaciones_en_lote(self._sesion, list(self._sesion.scalars(consulta)))

        regla = RepositorioCatalogos(self._sesion).regla_vigente()
        parametros = ParametrosRegla.desde_json(regla.parametros) if regla else None
        unidades = {u.id_unidad: u for u in self._sesion.scalars(select(UnidadOrganica))}
        metas = {m.id_meta: m for m in self._sesion.scalars(select(MetaPresupuestal))}
        saldos = self._saldos_disponibles({m.anio_fiscal for m in metas.values()}, parametros)

        pares = [(self._fila(s, unidades, metas, saldos, ahora), s) for s in situaciones]
        tarjetas = _tarjetas(pares)
        filas = _ordenar([fila for fila, s in pares if _pasa_filtros(fila, s, filtros)],
                         filtros.orden, filtros.descendente)
        paginas = max(1, math.ceil(len(filas) / POR_PAGINA))
        pagina = min(max(1, filtros.pagina), paginas)
        corte = self._presupuesto.ultima_carga_exitosa("MEF", fecha_local(ahora).year)
        usadas = {(fila.meta_codigo, fila.meta_nombre) for fila, _ in pares}
        return TableroSalida(
            tarjetas=tarjetas, fecha_corte_mef=corte.fecha_corte if corte else None,
            unidad=unidad_texto,
            metas=[MetaFiltro(codigo=c, nombre=n) for c, n in sorted(usadas)],
            filas=filas[(pagina - 1) * POR_PAGINA: pagina * POR_PAGINA],
            total_filas=len(filas), pagina=pagina, paginas=paginas, por_pagina=POR_PAGINA)

    def _saldos_disponibles(self, anios: set[int],
                            parametros: ParametrosRegla | None) -> dict[int, Decimal]:
        """Saldo presupuestal disponible de cada meta en la última carga exitosa del MEF.

        Se calcula con la columna de la regla vigente, igual que el semáforo (RF-02); es
        crédito presupuestario aún no comprometido, no dinero en caja.
        """
        saldos: dict[int, Decimal] = {}
        if parametros is None:
            return saldos
        for anio in anios:
            carga = self._presupuesto.ultima_carga_exitosa("MEF", anio)
            if carga is None:
                continue
            for id_meta, s in self._presupuesto.saldos_de_carga(carga.id_carga).items():
                vigente = SaldoVigente(s.pim, s.certificacion, s.compromiso_anual,
                                       carga.fecha_corte)
                saldos[id_meta] = calcular_saldo_disponible(vigente, parametros)
        return saldos

    @staticmethod
    def _fila(s: Situacion, unidades: dict, metas: dict, saldos: dict[int, Decimal],
              ahora: datetime) -> FilaTablero:
        req, cerrado = s.requerimiento, s.estado.es_final
        meta = metas[req.id_meta]
        horas = None if cerrado else s.horas_en_etapa(ahora)
        return FilaTablero(
            requerimiento_id=req.id_requerimiento, codigo=req.codigo,
            descripcion=req.descripcion, objeto_contratacion=req.objeto_contratacion,
            unidad_sigla=unidades[req.id_unidad].sigla or "—", meta_codigo=meta.codigo,
            meta_nombre=meta.nombre, monto_estimado=req.monto_estimado,
            saldo_disponible=saldos.get(req.id_meta), fecha_necesidad=req.fecha_necesidad,
            semaforo_vigente=str(s.vigente), estado_codigo=s.codigo_estado,
            estado_actual=s.estado.nombre,
            horas_en_etapa=round(horas, 1) if horas is not None else None,
            plazo_horas=None if cerrado else s.estado.plazo_horas,
            cuello_de_botella=not cerrado and s.excedido(ahora), cerrado=cerrado)
