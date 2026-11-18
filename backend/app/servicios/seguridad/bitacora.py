"""Bitácora de auditoría encadenada por hash (RNF-03; Tablas 17 y 18 de la Práctica 5).

Cada registro guarda en hash_anterior el resumen SHA-256 del registro previo. Si alguien
modificara o borrara un registro, la cadena dejaría de coincidir desde ese punto; además,
la base de datos rechaza UPDATE y DELETE sobre la tabla (RI-22). El registro se escribe en la
misma transacción que la operación auditada: si la operación se revierte, el registro también.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modelos.seguridad import Bitacora

# Bloqueo de transacción que serializa la escritura de la cadena (dos inserciones simultáneas
# no pueden tomar el mismo registro previo).
_LLAVE_BLOQUEO = 4_208_201
_ULTIMO_EN_TRANSACCION = "bitacora_ultimo_registro"


@dataclass(frozen=True)
class Contexto:
    """Datos de la petición que acompañan a cada registro."""

    ip_origen: str | None = None
    id_traza: uuid.UUID = field(default_factory=uuid.uuid4)


def resumen_registro(r: Bitacora) -> str:
    partes = [
        str(r.id_bitacora), r.fecha_hora.astimezone(UTC).isoformat(), str(r.id_usuario),
        str(r.id_rol), str(r.actor_servicio), r.accion, str(r.recurso_tipo), str(r.recurso_id),
        r.resultado, json.dumps(r.detalle, sort_keys=True, ensure_ascii=False),
        str(r.id_traza), str(r.hash_anterior),
    ]
    return hashlib.sha256("|".join(partes).encode()).hexdigest()


def registrar(
    sesion: Session, momento: datetime, contexto: Contexto, accion: str, resultado: str, *,
    id_usuario: int | None = None, id_rol: int | None = None, recurso_tipo: str | None = None,
    recurso_id: int | None = None, detalle: dict[str, Any] | None = None,
    actor_servicio: str | None = None,
) -> Bitacora:
    # Dentro de una misma transacción, el bloqueo ya está tomado y el registro previo es el
    # que se acaba de insertar: no hace falta volver a pedirlos (defecto DEF-02, P9).
    transaccion = sesion.get_transaction()
    anterior = sesion.info.get(_ULTIMO_EN_TRANSACCION)
    if anterior is not None and anterior[0] is transaccion:
        previo = anterior[1]
    else:
        sesion.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LLAVE_BLOQUEO})
        previo = sesion.scalar(select(Bitacora).order_by(Bitacora.id_bitacora.desc()).limit(1))
    registro = Bitacora(
        fecha_hora=momento, id_usuario=id_usuario, id_rol=id_rol, actor_servicio=actor_servicio,
        accion=accion,
        recurso_tipo=recurso_tipo, recurso_id=recurso_id, resultado=resultado,
        detalle=detalle, ip_origen=contexto.ip_origen, id_traza=contexto.id_traza,
        hash_anterior=resumen_registro(previo) if previo else None,
    )
    sesion.add(registro)
    sesion.flush()
    sesion.info[_ULTIMO_EN_TRANSACCION] = (transaccion, registro)
    return registro


def verificar_cadena(sesion: Session) -> int | None:
    """Recorre la bitácora y devuelve el id del primer registro roto, o None si está íntegra."""
    previo = None
    for registro in sesion.scalars(select(Bitacora).order_by(Bitacora.id_bitacora)):
        esperado = resumen_registro(previo) if previo else None
        if registro.hash_anterior != esperado:
            return registro.id_bitacora
        previo = registro
    return None
