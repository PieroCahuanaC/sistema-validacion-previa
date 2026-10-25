"""Acceso a la base presupuestal y al PAC."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos.presupuesto import CargaDatos, MetaPresupuestal, PacItem, SaldoMeta


class RepositorioPresupuesto:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def ultima_carga_exitosa(self, fuente: str, anio_fiscal: int) -> CargaDatos | None:
        """Última carga válida de la fuente (índice I-07; RI-17)."""
        return self._sesion.scalar(
            select(CargaDatos)
            .where(CargaDatos.fuente == fuente, CargaDatos.resultado == "EXITOSA",
                   CargaDatos.anio_fiscal == anio_fiscal)
            .order_by(CargaDatos.fecha_corte.desc(), CargaDatos.id_carga.desc())
            .limit(1)
        )

    def meta_activa(self, anio_fiscal: int, codigo: str) -> MetaPresupuestal | None:
        return self._sesion.scalar(
            select(MetaPresupuestal).where(
                MetaPresupuestal.anio_fiscal == anio_fiscal,
                MetaPresupuestal.codigo == codigo,
                MetaPresupuestal.activa.is_(True),
            )
        )

    def metas_activas(self, anio_fiscal: int) -> list[MetaPresupuestal]:
        return list(self._sesion.scalars(
            select(MetaPresupuestal)
            .where(MetaPresupuestal.anio_fiscal == anio_fiscal, MetaPresupuestal.activa.is_(True))
            .order_by(MetaPresupuestal.codigo)
        ))

    def saldo(self, id_meta: int, id_carga: int) -> SaldoMeta | None:
        return self._sesion.scalar(
            select(SaldoMeta).where(SaldoMeta.id_meta == id_meta, SaldoMeta.id_carga == id_carga)
        )

    def saldos_de_carga(self, id_carga: int) -> dict[int, SaldoMeta]:
        saldos = self._sesion.scalars(select(SaldoMeta).where(SaldoMeta.id_carga == id_carga))
        return {s.id_meta: s for s in saldos}

    def pac_item(self, id_carga: int, numero_referencia: str) -> PacItem | None:
        return self._sesion.scalar(
            select(PacItem).where(PacItem.id_carga == id_carga,
                                  PacItem.numero_referencia == numero_referencia)
        )

    def pac_items(self, id_carga: int) -> list[PacItem]:
        return list(self._sesion.scalars(
            select(PacItem).where(PacItem.id_carga == id_carga)
            .order_by(PacItem.numero_referencia)
        ))

    def obtener_saldo(self, id_saldo: int) -> SaldoMeta | None:
        return self._sesion.get(SaldoMeta, id_saldo)

    def obtener_carga(self, id_carga: int) -> CargaDatos | None:
        return self._sesion.get(CargaDatos, id_carga)

    def obtener_meta(self, id_meta: int) -> MetaPresupuestal | None:
        return self._sesion.get(MetaPresupuestal, id_meta)

    def obtener_pac_item(self, id_pac_item: int) -> PacItem | None:
        return self._sesion.get(PacItem, id_pac_item)
