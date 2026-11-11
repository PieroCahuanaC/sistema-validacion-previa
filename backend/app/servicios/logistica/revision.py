"""Validación documental (CU-07, RF-11; pantalla P09).

El Jefe de Logística y Abastecimientos revisa físicamente los documentos del expediente y
registra en el sistema el resultado de cada uno (Conforme u Observado, con su observación por
RI-11). Con todos los obligatorios conformes, el expediente pasa a Documentación validada y se
habilita el cuadro comparativo; con alguno observado, vuelve al Área Usuaria.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import DatosNoValidos, ErrorNegocio
from app.core.reloj import Reloj
from app.esquemas.logistica import (
    DocumentoRevision,
    RevisionEntrada,
    RevisionResultado,
    RevisionSalida,
)
from app.modelos.catalogos import Estado
from app.modelos.logistica import RevisionDocumento, TipoDocumento
from app.seguridad.dependencias import UsuarioActual
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto
from app.servicios.trazabilidad.maquina import MaquinaEstados
from app.servicios.validacion.situacion import situacion


class ServicioRevision:
    def __init__(self, sesion: Session, reloj: Reloj, contexto: Contexto) -> None:
        self._sesion = sesion
        self._reloj = reloj
        self._contexto = contexto
        self._maquina = MaquinaEstados(sesion, reloj, contexto)

    def _tipos(self) -> list[TipoDocumento]:
        return list(self._sesion.scalars(select(TipoDocumento)
                                         .where(TipoDocumento.activo.is_(True))
                                         .order_by(TipoDocumento.id_tipo_documento)))

    def consultar(self, id_requerimiento: int, usuario: UsuarioActual) -> RevisionSalida:
        requerimiento = self._maquina.obtener(id_requerimiento, usuario)
        documentos = []
        for tipo in self._tipos():
            ultima = self._sesion.scalar(
                select(RevisionDocumento)
                .where(RevisionDocumento.id_requerimiento == id_requerimiento,
                       RevisionDocumento.id_tipo_documento == tipo.id_tipo_documento)
                .order_by(RevisionDocumento.fecha_hora.desc(),
                          RevisionDocumento.id_revision.desc()).limit(1))
            documentos.append(DocumentoRevision(
                id_tipo_documento=tipo.id_tipo_documento, nombre=tipo.nombre,
                obligatorio=tipo.obligatorio,
                ultimo_resultado=ultima.resultado if ultima else None,
                ultima_observacion=ultima.observacion if ultima else None,
                ultima_fecha=ultima.fecha_hora if ultima else None))
        estado = self._sesion.get(Estado, requerimiento.id_estado_actual)
        return RevisionSalida(requerimiento_id=id_requerimiento, documentos=documentos,
                              puede_revisar=estado.codigo == "APROBADO"
                              and usuario.codigo_rol == "JL")

    def registrar(self, id_requerimiento: int, datos: RevisionEntrada,
                  usuario: UsuarioActual) -> RevisionResultado:
        requerimiento = self._maquina.bloquear(id_requerimiento, usuario)
        if situacion(self._sesion, requerimiento).codigo_estado != "APROBADO":
            raise ErrorNegocio(409, "Conflicto", "Solo se revisan los documentos de un "
                               "requerimiento Aprobado por la Gerencia de Administración.")
        tipos = {t.id_tipo_documento: t for t in self._tipos()}
        recibidos = [d.id_tipo_documento for d in datos.documentos]
        if sorted(recibidos) != sorted(tipos):
            raise DatosNoValidos("Registre el resultado de cada documento del expediente, "
                                 "una sola vez.")
        observados = []
        for documento in datos.documentos:
            observacion = (documento.observacion or "").strip() or None
            nombre = tipos[documento.id_tipo_documento].nombre
            if documento.resultado == "OBSERVADO" and observacion is None:
                raise DatosNoValidos(f"Indique la observación de «{nombre}» (RI-11).")
            if documento.resultado == "OBSERVADO":
                observados.append(f"{nombre}: {observacion}")
        obligatorios_conformes = all(
            d.resultado == "CONFORME" for d in datos.documentos
            if tipos[d.id_tipo_documento].obligatorio)
        destino = "DOCUMENTACION_VALIDADA" if obligatorios_conformes else "OBSERVADO"
        transicion = self._maquina.verificar(requerimiento, destino, usuario)

        momento = self._reloj()
        for documento in datos.documentos:
            self._sesion.add(RevisionDocumento(
                id_requerimiento=id_requerimiento,
                id_tipo_documento=documento.id_tipo_documento, resultado=documento.resultado,
                observacion=(documento.observacion or "").strip() or None, fecha_hora=momento))
        self._sesion.flush()
        bitacora.registrar(
            self._sesion, momento, self._contexto, "REVISION_DOCUMENTO", "EXITO",
            id_usuario=usuario.id_usuario, id_rol=usuario.id_rol,
            recurso_tipo="REQUERIMIENTO", recurso_id=id_requerimiento,
            detalle={"resultados": {tipos[d.id_tipo_documento].nombre: d.resultado
                                    for d in datos.documentos}})
        observacion = "; ".join(observados)[:500] or None
        self._maquina.registrar(requerimiento, transicion, destino, observacion, usuario, momento)
        self._sesion.commit()
        return RevisionResultado(
            requerimiento_id=id_requerimiento, codigo=requerimiento.codigo,
            resultado="VALIDADA" if destino == "DOCUMENTACION_VALIDADA" else "DEVUELTA",
            estado_actual=self._sesion.get(Estado, requerimiento.id_estado_actual).nombre)
