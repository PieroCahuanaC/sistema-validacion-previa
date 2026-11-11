"""Pruebas unitarias de contraseñas y tokens de sesión (Tabla 13 de la Práctica 5)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jwt

from app.seguridad import contrasenas, tokens

AHORA = datetime(2026, 10, 25, 10, 0, tzinfo=ZoneInfo("America/Lima"))


def test_cpu31_contrasena_corta_comun_o_con_el_usuario_incumple_reglas():
    assert contrasenas.REGLAS[0] in contrasenas.incumplimientos("Corta1!", "jperez")
    assert contrasenas.REGLAS[1] in contrasenas.incumplimientos("Uchumayo2026!", "jperez")
    assert contrasenas.REGLAS[2] in contrasenas.incumplimientos("jperez-segura-77", "jperez")
    assert contrasenas.incumplimientos("aaaaaaaaaaaaaa", "jperez") == [contrasenas.REGLAS[1]]


def test_cpu32_contrasena_adecuada_no_tiene_incumplimientos():
    assert contrasenas.incumplimientos("Tarde de lluvia en Congata 7", "jperez") == []


def test_cpu33_hash_argon2id_verifica_y_no_guarda_texto_plano():
    hash_guardado = contrasenas.hashear("Tarde de lluvia en Congata 7")
    assert hash_guardado.startswith("$argon2id$")
    assert "Congata" not in hash_guardado
    assert contrasenas.verificar("Tarde de lluvia en Congata 7", hash_guardado)
    assert not contrasenas.verificar("otra cosa distinta", hash_guardado)
    assert not contrasenas.verificar("cualquiera", "no-es-un-hash")


def test_cpu34_contrasena_temporal_aleatoria_sin_caracteres_ambiguos():
    generadas = {contrasenas.generar_temporal() for _ in range(50)}
    assert len(generadas) == 50
    for temporal in generadas:
        assert len(temporal) == 16
        assert not set(temporal) & set("0OolI1")


def test_cpu35_token_de_acceso_vigente_15_minutos_segun_el_reloj_inyectado():
    token = tokens.emitir_acceso(7, "AU", 41, AHORA)
    carga = tokens.leer_acceso(token, AHORA + timedelta(minutes=14))
    assert carga["sub"] == "7" and carga["sid"] == 41 and carga["rol"] == "AU"
    assert tokens.leer_acceso(token, AHORA + timedelta(minutes=15)) is None


def test_cpu36_token_alterado_o_firmado_con_otra_clave_se_rechaza():
    token = tokens.emitir_acceso(7, "AU", 41, AHORA)
    alterado = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]
    ajeno = jwt.encode({"sub": "7", "sid": 41, "exp": 9_999_999_999}, "otra-clave",
                       algorithm="HS256")
    assert tokens.leer_acceso(alterado, AHORA) is None
    assert tokens.leer_acceso(ajeno, AHORA) is None
    assert tokens.leer_acceso("basura", AHORA) is None


def test_cpu37_token_de_renovacion_solo_se_guarda_como_resumen():
    token, resumen = tokens.nuevo_token_renovacion()
    assert len(resumen) == 64 and token not in resumen
    assert tokens.resumen(token) == resumen
