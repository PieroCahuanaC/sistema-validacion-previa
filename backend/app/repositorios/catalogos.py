"""Acceso a los catálogos (roles, unidades, estados, transiciones) y a la regla vigente."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos.catalogos import Estado, Rol, Transicion, UnidadOrganica
from app.modelos.configuracion import ReglaSemaforo


class RepositorioCatalogos:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def rol(self, codigo: str) -> Rol | None:
        return self._sesion.scalar(select(Rol).where(Rol.codigo == codigo))

    def roles_por_id(self) -> dict[int, Rol]:
        return {r.id_rol: r for r in self._sesion.scalars(select(Rol))}

    def unidad_por_sigla(self, sigla: str) -> UnidadOrganica | None:
        return self._sesion.scalar(
            select(UnidadOrganica).where(UnidadOrganica.sigla == sigla,
                                         UnidadOrganica.activa.is_(True))
        )

    def obtener_unidad(self, id_unidad: int) -> UnidadOrganica | None:
        return self._sesion.get(UnidadOrganica, id_unidad)

    def estado(self, codigo: str) -> Estado | None:
        return self._sesion.scalar(select(Estado).where(Estado.codigo == codigo))

    def estados(self) -> list[Estado]:
        return list(self._sesion.scalars(select(Estado).order_by(Estado.orden)))

    def transiciones(self) -> list[Transicion]:
        return list(self._sesion.scalars(select(Transicion)))

    def regla_vigente(self) -> ReglaSemaforo | None:
        """Única versión con vigente_hasta nulo (índice único parcial I-14; RI-03)."""
        return self._sesion.scalar(
            select(ReglaSemaforo).where(ReglaSemaforo.vigente_hasta.is_(None))
        )

    def obtener_regla(self, id_regla: int) -> ReglaSemaforo | None:
        return self._sesion.get(ReglaSemaforo, id_regla)
