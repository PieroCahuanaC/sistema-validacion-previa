"""Consultas de apoyo a la pantalla P03: metas con su saldo y el PAC vigente."""

from sqlalchemy.orm import Session

from app.esquemas.requerimiento import MetaSalida, PacItemSalida
from app.repositorios.presupuesto import RepositorioPresupuesto
from app.servicios.validacion.regla_semaforo import (
    ParametrosRegla,
    SaldoVigente,
    calcular_saldo_disponible,
)


def listar_metas(sesion: Session, anio: int, parametros: ParametrosRegla) -> list[MetaSalida]:
    """Metas activas con el saldo presupuestal disponible referencial y su fecha de corte."""
    repo = RepositorioPresupuesto(sesion)
    carga = repo.ultima_carga_exitosa("MEF", anio)
    saldos = repo.saldos_de_carga(carga.id_carga) if carga else {}
    salida = []
    for meta in repo.metas_activas(anio):
        saldo = saldos.get(meta.id_meta)
        disponible = None
        if saldo and carga and carga.fecha_corte:
            vigente = SaldoVigente(saldo.pim, saldo.certificacion, saldo.compromiso_anual,
                                   carga.fecha_corte)
            disponible = calcular_saldo_disponible(vigente, parametros)
        salida.append(MetaSalida(codigo=meta.codigo, nombre=meta.nombre,
                                 saldo_disponible=disponible,
                                 fecha_corte=carga.fecha_corte if saldo and carga else None))
    return salida


def listar_pac(sesion: Session, anio: int) -> list[PacItemSalida]:
    repo = RepositorioPresupuesto(sesion)
    carga = repo.ultima_carga_exitosa("SEACE", anio)
    if carga is None:
        return []
    return [PacItemSalida(numero_referencia=i.numero_referencia, descripcion=i.descripcion,
                          tipo_objeto=i.tipo_objeto, valor_estimado=i.valor_estimado)
            for i in repo.pac_items(carga.id_carga)]
