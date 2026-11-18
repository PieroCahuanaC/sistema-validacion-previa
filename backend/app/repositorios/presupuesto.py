"""Acceso a la base presupuestal y al PAC."""

from sqlalchemy import and_, select
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

    def ultima_carga_con_saldo(
        self, anio_fiscal: int, id_meta: int
    ) -> tuple[CargaDatos | None, SaldoMeta | None]:
        """Última carga exitosa del MEF y el saldo de la meta en ella, en una sola consulta
        (RI-17; defecto DEF-02 de la Práctica 9). El saldo es None si la meta no figura."""
        fila = self._sesion.execute(
            select(CargaDatos, SaldoMeta)
            .outerjoin(SaldoMeta, and_(SaldoMeta.id_carga == CargaDatos.id_carga,
                                       SaldoMeta.id_meta == id_meta))
            .where(CargaDatos.fuente == "MEF", CargaDatos.resultado == "EXITOSA",
                   CargaDatos.anio_fiscal == anio_fiscal)
            .order_by(CargaDatos.fecha_corte.desc(), CargaDatos.id_carga.desc())
            .limit(1)
        ).first()
        return (fila[0], fila[1]) if fila else (None, None)

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
