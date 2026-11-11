"""Pruebas unitarias de la protección de datos personales de proveedores (Ley N.° 29733)."""

import hashlib

from app.seguridad import cifrado


def test_cpu41_aes_gcm_cifra_con_nonce_distinto_y_descifra():
    primero, segundo = cifrado.cifrar("Juan Pérez Quispe"), cifrado.cifrar("Juan Pérez Quispe")
    assert primero != segundo and primero.startswith("v1:")
    assert "Juan" not in primero
    assert cifrado.descifrar(primero) == "Juan Pérez Quispe"
    assert len(cifrado.cifrar("x" * 300)) <= 500  # cabe en razon_social VARCHAR(500)


def test_cpu42_un_valor_alterado_no_se_descifra_y_lo_no_cifrado_se_devuelve_igual():
    valor = cifrado.cifrar("10467793549")
    alterado = valor[:-4] + ("AAAA" if not valor.endswith("AAAA") else "BBBB")
    assert cifrado.descifrar(alterado) == cifrado.NO_DISPONIBLE
    assert cifrado.descifrar("Constructora Andina S.A.C.") == "Constructora Andina S.A.C."


def test_cpu43_ruc_hash_es_hmac_con_clave_y_no_un_sha256_simple():
    resumen = cifrado.resumen_ruc("20100047218")
    assert resumen == cifrado.resumen_ruc("20100047218") and len(resumen) == 64
    assert resumen != hashlib.sha256(b"20100047218").hexdigest()


def test_cpu44_digito_verificador_del_ruc():
    assert cifrado.ruc_valido("20100047218")
    assert cifrado.ruc_valido("10467793549")
    assert not cifrado.ruc_valido("20100047219")
    assert not cifrado.ruc_valido("2010004721") and not cifrado.ruc_valido("2010004721A")
    assert cifrado.ocultar_ruc("10467793549") == "10•••••••49"
