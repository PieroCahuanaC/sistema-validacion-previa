"""Armado del detalle del requerimiento para la pantalla P04 (CU-04, RF-02, RF-03).

Incluye el indicador de etapas del trámite y el responsable actual que pidió el asesor en
la revisión de la Práctica 7.
"""

from sqlalchemy.orm import Session

from app.esquemas.requerimiento import (
    AccionesDisponibles,
    BaseCalculo,
    DecisionRegistrada,
    EtapaSalida,
    ItemSalida,
    ObservacionRecibida,
    RequerimientoDetalle,
    SemaforoSalida,
)
from app.modelos.catalogos import Estado, Rol, Transicion
from app.modelos.requerimiento import Requerimiento, ValidacionPresupuestal
from app.repositorios.catalogos import RepositorioCatalogos
from app.repositorios.presupuesto import RepositorioPresupuesto
from app.repositorios.requerimientos import RepositorioRequerimientos
from app.seguridad.dependencias import UsuarioActual
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
from app.servicios.validacion.situacion import Situacion, situacion
from app.servicios.validacion.vigencia import SemaforoVigente

ESTADOS_DEL_RECORRIDO = ("REGISTRADO", "APROBADO", "DOCUMENTACION_VALIDADA",
                         "CUADRO_REGISTRADO", "CERTIFICADO", "ORDEN_EMITIDA")

# Mientras el requerimiento está en REGISTRADO, quién actúa depende del semáforo vigente
# (RI-20) y de si el Área Usuaria ya lo envió desde el paso 2 (cambio 15 de la Práctica 7).
PENDIENTE_POR_SEMAFORO = {
    SemaforoVigente.AMBAR_PENDIENTE: ("JP", "Confirmar o denegar la disponibilidad presupuestal"),
    SemaforoVigente.AMBAR_DENEGADO: ("AU", "Anular el requerimiento"),
    SemaforoVigente.ROJO: ("AU", "Aplicar un ajuste al requerimiento"),
}
PENDIENTE_VERDE_SIN_ENVIAR = ("AU", "Completar el paso 2 y enviar a la Gerencia de Administración")
PENDIENTE_VERDE_ENVIADO = ("GA", "Aprobar u observar el requerimiento")


def _rol_a_cargo(estado: Estado, transiciones: list[Transicion], roles: dict[int, Rol]) -> str:
    """Rol que registra el ingreso a la etapa; el registro inicial lo hace el Área Usuaria."""
    if estado.codigo == "REGISTRADO":
        return next(r.nombre for r in roles.values() if r.codigo == "AU")
    for t in transiciones:
        if t.id_estado_destino == estado.id_estado and t.tipo == "AVANCE":
            return roles[t.id_rol].nombre
    return "—"


def _pendiente_en_registrado(vigente: SemaforoVigente, enviado: bool,
                             opcion_ajuste: str | None) -> tuple[str, str]:
    if vigente == SemaforoVigente.VERDE:
        return PENDIENTE_VERDE_ENVIADO if enviado else PENDIENTE_VERDE_SIN_ENVIAR
    if vigente == SemaforoVigente.ROJO and opcion_ajuste == "NINGUNA":
        return "AU", "Anular el requerimiento"
    return PENDIENTE_POR_SEMAFORO[vigente]


def responsable_actual(sesion: Session, s: Situacion) -> tuple[str, str]:
    """Rol que debe actuar ahora sobre el requerimiento y qué debe hacer (P04 y P07)."""
    catalogos = RepositorioCatalogos(sesion)
    return _responsable(s.estado, s.vigente, s.enviado, s.opcion_ajuste,
                        catalogos.transiciones(), catalogos.roles_por_id(),
                        {e.id_estado: e for e in catalogos.estados()})


def _responsable(
    estado: Estado, vigente: SemaforoVigente, enviado: bool, opcion_ajuste: str | None,
    transiciones: list[Transicion], roles: dict[int, Rol], estados: dict[int, Estado],
) -> tuple[str, str]:
    por_codigo = {r.codigo: r.nombre for r in roles.values()}
    if estado.es_final:
        return "—", "Trámite cerrado"
    if estado.codigo == "REGISTRADO":
        codigo_rol, accion = _pendiente_en_registrado(vigente, enviado, opcion_ajuste)
        return por_codigo[codigo_rol], accion
    if estado.codigo == "OBSERVADO":
        return por_codigo["AU"], "Subsanar la observación y reenviar"
    for t in transiciones:
        if t.id_estado_origen == estado.id_estado and t.tipo == "AVANCE":
            return roles[t.id_rol].nombre, f"Registrar {estados[t.id_estado_destino].nombre}"
    return "—", "—"


def construir_detalle(sesion: Session, requerimiento: Requerimiento,
                      usuario: UsuarioActual | None = None) -> RequerimientoDetalle:
    catalogos = RepositorioCatalogos(sesion)
    presupuesto = RepositorioPresupuesto(sesion)
    requerimientos = RepositorioRequerimientos(sesion)

    roles = catalogos.roles_por_id()
    estados = {e.id_estado: e for e in catalogos.estados()}
    transiciones = catalogos.transiciones()
    actual = situacion(sesion, requerimiento)
    estado_actual = actual.estado
    validacion = actual.validacion
    regla = catalogos.obtener_regla(validacion.id_regla)
    if regla is None:
        raise RuntimeError("La validación referencia una regla inexistente (R14).")
    # Se usa la versión de la regla con la que se calculó el semáforo, no la vigente (R14).
    semaforo = _semaforo(presupuesto, requerimiento, validacion,
                         ParametrosRegla.desde_json(regla.parametros))
    vigente = actual.vigente
    enviado = actual.enviado
    responsable, accion = _responsable(estado_actual, vigente, enviado, actual.opcion_ajuste,
                                       transiciones, roles, estados)

    registros = requerimientos.historial(requerimiento.id_requerimiento)
    historial = {h.id_estado: h for h in registros}
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

    observacion_recibida = None
    if estado_actual.codigo == "OBSERVADO" and registros:
        ultimo = registros[-1]
        observacion_recibida = ObservacionRecibida(
            texto=ultimo.observacion or "", rol=roles[ultimo.id_rol].nombre,
            fecha_hora=ultimo.fecha_hora)
    decision = None
    if actual.decision is not None:
        decision = DecisionRegistrada(
            resultado=actual.decision.resultado, sustento=actual.decision.sustento,
            fecha_hora=actual.decision.fecha_hora,
            rol=next(r.nombre for r in roles.values() if r.codigo == "JP"))
    es_area_usuaria = usuario is None or usuario.codigo_rol == "AU"
    acciones = AccionesDisponibles(
        aplicar_ajuste=es_area_usuaria and actual.puede_aplicar_ajuste,
        anular=es_area_usuaria and actual.puede_anular,
        subsanar=es_area_usuaria and actual.puede_subsanar,
    )

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
        items=[ItemSalida(id_item=i.id_item, descripcion=i.descripcion,
                          especificacion=i.especificacion, unidad_medida=i.unidad_medida,
                          cantidad=i.cantidad, precio_unitario_ref=i.precio_unitario_ref,
                          fuente_precio=i.fuente_precio, subtotal=subtotal(i))
               for i in requerimiento.items],
        etapas=etapas, semaforo=semaforo,
        semaforo_vigente=vigente,
        confirmado_por_presupuesto=actual.confirmado_por_presupuesto,
        plazo_entrega_dias=requerimiento.plazo_entrega_dias,
        lugar_entrega=requerimiento.lugar_entrega, fecha_envio=requerimiento.fecha_envio,
        puede_completar_paso_2=(es_area_usuaria and estado_actual.codigo == "REGISTRADO"
                                and not enviado and vigente == SemaforoVigente.VERDE),
        opcion_ajuste=actual.opcion_ajuste,
        observacion_recibida=observacion_recibida, decision_presupuesto=decision,
        acciones=acciones,
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
