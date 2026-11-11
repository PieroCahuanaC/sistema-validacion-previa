"""Pruebas de integración del inicio de sesión (CU-09, RF-10; Tabla 13 de la Práctica 5)."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modelos.seguridad import Bitacora, SesionUsuario
from app.seguridad import tokens
from app.servicios.seguridad.bitacora import verificar_cadena

INGRESO = "/api/v1/auth/ingreso"
RENOVACION = "/api/v1/auth/renovacion"
INICIO = "/api/v1/inicio"


def ingresar(c, nombre, contrasena):
    return c.post(INGRESO, json={"nombre_usuario": nombre, "contrasena": contrasena})


def test_cpi22_ingreso_correcto_entrega_cookies_seguras_y_datos_del_usuario(
        reloj_movil, nuevo_usuario, sesion):
    c, _ = reloj_movil
    nombre, contrasena, id_usuario = nuevo_usuario("AU", "GDUR")
    r = ingresar(c, nombre.upper(), contrasena)  # el usuario no distingue mayúsculas
    assert r.status_code == 200, r.text
    assert r.json()["rol"]["codigo"] == "AU" and r.json()["unidad"]["sigla"] == "GDUR"
    assert r.json()["contrasena_temporal"] is False
    cookies = r.headers.get_list("set-cookie")
    for nombre_cookie in (tokens.COOKIE_ACCESO, tokens.COOKIE_RENOVACION):
        linea = next(x for x in cookies if x.startswith(nombre_cookie + "="))
        assert "HttpOnly" in linea and "SameSite=strict" in linea
    assert contrasena not in r.text and "hash" not in r.text
    assert c.get("/api/v1/auth/yo").json()["id_usuario"] == id_usuario
    assert c.get(INICIO).status_code == 200
    ultimo = sesion.scalar(select(Bitacora).order_by(Bitacora.id_bitacora.desc()).limit(1))
    assert ultimo.accion == "LOGIN_EXITOSO" and ultimo.id_usuario == id_usuario


def test_cpi23_sin_sesion_o_con_cookie_falsificada_responde_401(reloj_movil):
    c, _ = reloj_movil
    assert c.get(INICIO).status_code == 401
    assert c.get("/api/v1/metas").status_code == 401
    falsa = TestClient(c.app, headers={"Cookie": f"{tokens.COOKIE_ACCESO}=eyJhbGciOi.x.y"})
    assert falsa.get(INICIO).status_code == 401


def test_cpi24_tres_intentos_fallidos_bloquean_15_minutos(reloj_movil, nuevo_usuario):
    c, reloj = reloj_movil
    nombre, contrasena, _ = nuevo_usuario()
    desconocido = ingresar(c, "no.existe", "lo-que-sea-123")
    assert desconocido.status_code == 401 and "intentos_restantes" not in desconocido.json()

    primero = ingresar(c, nombre, "incorrecta-1")
    assert primero.status_code == 401
    assert primero.json()["detail"] == "Usuario o contraseña incorrectos."
    assert primero.json()["intentos_restantes"] == 2
    assert ingresar(c, nombre, "incorrecta-2").json()["intentos_restantes"] == 1
    tercero = ingresar(c, nombre, "incorrecta-3")
    assert tercero.status_code == 423 and "bloqueado_hasta" in tercero.json()

    assert ingresar(c, nombre, contrasena).status_code == 423  # aún con la contraseña correcta
    reloj.adelantar(minutes=15, seconds=1)
    assert ingresar(c, nombre, contrasena).status_code == 200


def test_cpi25_contrasena_temporal_obliga_a_cambiarla_con_reglas(reloj_movil, nuevo_usuario):
    c, _ = reloj_movil
    nombre, temporal, _ = nuevo_usuario(temporal=True)
    r = ingresar(c, nombre, temporal)
    assert r.status_code == 200 and r.json()["contrasena_temporal"] is True
    assert len(r.json()["reglas_contrasena"]) == 3
    assert c.get(INICIO).status_code == 403  # no puede usar el sistema todavía

    cambio = "/api/v1/auth/cambio-contrasena"
    debil = c.post(cambio, json={"contrasena_actual": temporal, "contrasena_nueva": "corta"})
    assert debil.status_code == 422 and debil.json()["reglas"]
    mala = c.post(cambio, json={"contrasena_actual": "otra", "contrasena_nueva": "x" * 20})
    assert mala.status_code == 422
    nueva = "Tarde de lluvia en Congata 7"
    assert c.post(cambio, json={"contrasena_actual": temporal,
                                "contrasena_nueva": nueva}).status_code == 204
    assert c.get(INICIO).status_code == 200
    assert c.get("/api/v1/auth/yo").json()["contrasena_temporal"] is False
    assert ingresar(c, nombre, temporal).status_code == 401
    assert ingresar(c, nombre, nueva).status_code == 200


def test_cpi26_renovacion_rota_el_token_y_su_reuso_cierra_todas_las_sesiones(
        reloj_movil, nuevo_usuario, sesion):
    c, _ = reloj_movil
    nombre, contrasena, id_usuario = nuevo_usuario()
    ingresar(c, nombre, contrasena)
    anterior = c.cookies.get(tokens.COOKIE_RENOVACION)
    assert c.post(RENOVACION).status_code == 204
    assert c.cookies.get(tokens.COOKIE_RENOVACION) != anterior
    assert c.get(INICIO).status_code == 200

    # Alguien reutiliza el token ya rotado (por ejemplo, robado): se cierran todas las sesiones.
    atacante = TestClient(c.app, headers={"Cookie": f"{tokens.COOKIE_RENOVACION}={anterior}"})
    assert atacante.post(RENOVACION).status_code == 401
    assert c.get(INICIO).status_code == 401
    assert c.post(RENOVACION).status_code == 401
    vigentes = sesion.scalars(select(SesionUsuario).where(
        SesionUsuario.id_usuario == id_usuario, SesionUsuario.revocada_en.is_(None))).all()
    assert vigentes == []


def test_cpi27_acceso_vence_a_los_15_minutos_y_la_sesion_a_las_8_horas(
        reloj_movil, nuevo_usuario):
    c, reloj = reloj_movil
    nombre, contrasena, _ = nuevo_usuario()
    ingresar(c, nombre, contrasena)
    reloj.adelantar(minutes=16)
    assert c.get(INICIO).status_code == 401
    assert c.post(RENOVACION).status_code == 204  # el frontend renueva y reintenta
    assert c.get(INICIO).status_code == 200
    reloj.adelantar(hours=8)  # la rotación no extiende el máximo de 8 horas
    assert c.post(RENOVACION).status_code == 401


def test_cpi28_cerrar_sesion_revoca_la_sesion_y_borra_las_cookies(reloj_movil, nuevo_usuario):
    c, _ = reloj_movil
    nombre, contrasena, _ = nuevo_usuario()
    ingresar(c, nombre, contrasena)
    acceso = c.cookies.get(tokens.COOKIE_ACCESO)
    r = c.post("/api/v1/auth/salida")
    assert r.status_code == 204
    assert c.get(INICIO).status_code == 401
    assert c.post(RENOVACION).status_code == 401
    # Aunque alguien hubiera copiado la cookie de acceso, la sesión ya está revocada.
    copia = TestClient(c.app, headers={"Cookie": f"{tokens.COOKIE_ACCESO}={acceso}"})
    assert copia.get(INICIO).status_code == 401


def test_cpi29_operacion_desde_un_origen_ajeno_se_rechaza(reloj_movil, nuevo_usuario):
    c, _ = reloj_movil
    nombre, contrasena, _ = nuevo_usuario()
    r = c.post(INGRESO, json={"nombre_usuario": nombre, "contrasena": contrasena},
               headers={"Origin": "https://sitio-malicioso.example"})
    assert r.status_code == 403 and r.json()["detail"] == "Origen no permitido."
    permitido = c.post(INGRESO, json={"nombre_usuario": nombre, "contrasena": contrasena},
                       headers={"Origin": "http://localhost:4321"})
    assert permitido.status_code == 200


def test_cpi30_bitacora_encadenada_integra_y_sin_contrasenas(reloj_movil, nuevo_usuario,
                                                              sesion):
    c, _ = reloj_movil
    nombre, contrasena, _ = nuevo_usuario()
    ingresar(c, nombre, "incorrecta-para-bitacora")
    ingresar(c, nombre, contrasena)
    assert verificar_cadena(sesion) is None
    for registro in sesion.scalars(select(Bitacora)):
        texto = str(registro.detalle or "")
        assert contrasena not in texto and "incorrecta-para-bitacora" not in texto
