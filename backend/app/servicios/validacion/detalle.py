"""Armado del detalle del requerimiento para la pantalla P04 (CU-04, RF-02, RF-03).

Incluye el indicador de etapas del trámite y el responsable actual que pidió el asesor en
la revisión de la Práctica 7.
"""

from sqlalchemy.orm import Session

from app.esquemas.requerimiento import (
    BaseCalculo,
    EtapaSalida,
    ItemSalida,
    RequerimientoDetalle,
    SemaforoSalida,
)
from app.modelos.catalogos import Estado, Rol, Transicion
from app.modelos.requerimiento import Requerimiento, ValidacionPresupuestal
from app.repositorios.catalogos import RepositorioCatalogos
from app.repositorios.presupuesto import RepositorioPresupuesto
from app.repositorios.requerimientos import RepositorioRequerimientos
from app.servicios.validacion.monto import subtotal
from app.servicios.validacion.regla_semaforo import (
    Motivo,
    ParametrosRegla,
    ResultadoSemaforo,
    SaldoVigente,
    Semaforo,
    calcular_saldo_disponible,
    opciones_de_ajuste,
)

ESTADOS_DEL_RECORRIDO = ("REGISTRADO", "APROBADO", "DOCUMENTACION_VALIDADA",
                         "CUADRO_REGISTRADO", "CERTIFICADO", "ORDEN_EMITIDA")

# Mientras el requerimiento está en REGISTRADO, quién actúa depende del semáforo vigente.
PENDIENTE_POR_SEMAFORO = {
    Semaforo.VERDE: ("GA", "Aprobar u observar el requerimiento"),
    Semaforo.AMBAR: ("JP", "Confirmar o denegar la disponibilidad presupuestal"),
    Semaforo.ROJO: ("AU", "Aplicar un ajuste al requerimiento"),
}


def _rol_a_cargo(estado: Estado, transiciones: list[Transicion], roles: dict[int, Rol]) -> str:
    """Rol que registra el ingreso a la etapa; el registro inicial lo hace el Área Usuaria."""
    if estado.codigo == "REGISTRADO":
        return next(r.nombre for r in roles.values() if r.codigo == "AU")
    for t in transiciones:
        if t.id_estado_destino == estado.id_estado and t.tipo == "AVANCE":
            return roles[t.id_rol].nombre
    return "—"


def _responsable(
    estado: Estado, semaforo: Semaforo, transiciones: list[Transicion], roles: dict[int, Rol],
    estados: dict[int, Estado],
) -> tuple[str, str]:
    por_codigo = {r.codigo: r.nombre for r in roles.values()}
    if estado.es_final:
        return "—", "Trámite cerrado"
    if estado.codigo == "REGISTRADO":
        codigo_rol, accion = PENDIENTE_POR_SEMAFORO[semaforo]
        return por_codigo[codigo_rol], accion
    if estado.codigo == "OBSERVADO":
        return por_codigo["AU"], "Subsanar la observación y reenviar"
    for t in transiciones:
        if t.id_estado_origen == estado.id_estado and t.tipo == "AVANCE":
            return roles[t.id_rol].nombre, f"Registrar {estados[t.id_estado_destino].nombre}"
    return "—", "—"


def construir_detalle(sesion: Session, requerimiento: Requerimiento) -> RequerimientoDetalle:
    catalogos = RepositorioCatalogos(sesion)
    presupuesto = RepositorioPresupuesto(sesion)
    requerimientos = RepositorioRequerimientos(sesion)

    roles = catalogos.roles_por_id()
    estados = {e.id_estado: e for e in catalogos.estados()}
    transiciones = catalogos.transiciones()
    estado_actual = estados[requerimiento.id_estado_actual]
    validacion = requerimientos.ultima_validacion(requerimiento.id_requerimiento)
    if validacion is None:
        raise RuntimeError("Todo requerimiento tiene al menos una validación (R12).")
    regla = catalogos.obtener_regla(validacion.id_regla)
    if regla is None:
        raise RuntimeError("La validación referencia una regla inexistente (R14).")
    # Se usa la versión de la regla con la que se calculó el semáforo, no la vigente (R14).
    semaforo = _semaforo(presupuesto, requerimiento, validacion,
                         ParametrosRegla.desde_json(regla.parametros))
    responsable, accion = _responsable(estado_actual, Semaforo(semaforo.estado), transiciones,
                                       roles, estados)

    historial = {h.id_estado: h for h in requerimientos.historial(requerimiento.id_requerimiento)}
    etapas = []
    for codigo in ESTADOS_DEL_RECORRIDO:
        estado = next(e for e in estados.values() if e.codigo == codigo)
        registro = historial.get(estado.id_estado)
        etapas.append(EtapaSalida(
            codigo=estado.codigo, nombre=estado.nombre,
            rol_a_cargo=_rol_a_cargo(estado, transiciones, roles),
            cumplida=registro is not None, actual=estado.id_estado == estado_actual.id_estado,
            fecha_hora=registro.fecha_hora if registro else None,
            rol_registro=roles[registro.id_rol].nombre if registro else None,
            observacion=registro.observacion if registro else None,
        ))

    meta = presupuesto.obtener_meta(requerimiento.id_meta)
    unidad = catalogos.obtener_unidad(requerimiento.id_unidad)
    return RequerimientoDetalle(
        requerimiento_id=requerimiento.id_requerimiento, codigo=requerimiento.codigo,
        unidad_organica=unidad.nombre if unidad else "—",
        meta_codigo=meta.codigo if meta else "—", meta_nombre=meta.nombre if meta else "—",
        objeto_contratacion=requerimiento.objeto_contratacion,
        descripcion=requerimiento.descripcion, monto_estimado=requerimiento.monto_estimado,
        fecha_necesidad=requerimiento.fecha_necesidad,
        fecha_registro=requerimiento.fecha_registro, estado_actual=estado_actual.nombre,
        responsable_actual=responsable, accion_pendiente=accion,
        items=[ItemSalida(descripcion=i.descripcion, unidad_medida=i.unidad_medida,
                          cantidad=i.cantidad, precio_unitario_ref=i.precio_unitario_ref,
                          fuente_precio=i.fuente_precio, subtotal=subtotal(i))
               for i in requerimiento.items],
        etapas=etapas, semaforo=semaforo,
    )


def _semaforo(
    presupuesto: RepositorioPresupuesto, requerimiento: Requerimiento,
    validacion: ValidacionPresupuestal, parametros: ParametrosRegla,
) -> SemaforoSalida:
    saldo = presupuesto.obtener_saldo(validacion.id_saldo) if validacion.id_saldo else None
    carga = presupuesto.obtener_carga(saldo.id_carga) if saldo else None
    pac = (presupuesto.obtener_pac_item(requerimiento.id_pac_item)
           if requerimiento.id_pac_item else None)
    disponible = None
    if saldo and carga and carga.fecha_corte:
        vigente = SaldoVigente(saldo.pim, saldo.certificacion, saldo.compromiso_anual,
                               carga.fecha_corte)
        disponible = calcular_saldo_disponible(vigente, parametros)
    resultado = ResultadoSemaforo(Semaforo(validacion.estado_semaforo),
                                  Motivo(validacion.motivo), disponible)
    return SemaforoSalida(
        estado=validacion.estado_semaforo, motivo=validacion.motivo,
        fecha_hora=validacion.fecha_hora,
        base_calculo=BaseCalculo(
            pim=saldo.pim if saldo else None,
            certificacion=saldo.certificacion if saldo else None,
            compromiso_anual=saldo.compromiso_anual if saldo else None,
            columna_comparacion=parametros.columna_comparacion,
            saldo_disponible=disponible, monto_evaluado=validacion.monto_evaluado,
            fecha_corte=carga.fecha_corte if carga else None,
            previsto_en_pac=pac is not None,
            pac_item_referencia=pac.numero_referencia if pac else None,
        ),
        opciones_ajuste=opciones_de_ajuste(resultado),
    )
