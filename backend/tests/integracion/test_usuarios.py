"""Pruebas de integración de la gestión de usuarios (P16, CU-15, RF-15) y de la P02."""

from sqlalchemy import select

from app.modelos.seguridad import Bitacora

USUARIOS = "/api/v1/usuarios"
INICIO = "/api/v1/inicio"


def ingresar(c, nombre, contrasena):
    return c.post("/api/v1/auth/ingreso", json={"nombre_usuario": nombre, "contrasena": contrasena})


def test_cpi31_solo_el_administrador_gestiona_usuarios(como, sesion):
    for rol in ("AU", "GA", "JL", "JP"):
        assert como(rol).get(USUARIOS).status_code == 403
    denegado = sesion.scalar(select(Bitacora).order_by(Bitacora.id_bitacora.desc()).limit(1))
    assert denegado.accion == "ACCESO_DENEGADO"
    assert denegado.detalle == {"metodo": "GET", "ruta": USUARIOS}
    admin = como("ADM")
    assert admin.get(USUARIOS).status_code == 200
    catalogos = admin.get(f"{USUARIOS}/catalogos").json()
    assert {r["codigo"] for r in catalogos["roles"]} >= {"AU", "GA", "JL", "JP", "ADM"}


def test_cpi32_alta_con_contrasena_temporal_y_validaciones(como, reloj_movil, sesion):
    admin = como("ADM")
    base = {"nombre_usuario": "mquispe.gdur", "nombres_apellidos": "María Quispe Ficticia",
            "codigo_rol": "AU", "unidad_sigla": "GDUR"}
    sin_unidad = admin.post(USUARIOS, json={**base, "unidad_sigla": None})
    assert sin_unidad.status_code == 422  # RI-13
    con_dni = admin.post(USUARIOS, json={**base, "nombre_usuario": "mq.40123456"})
    assert con_dni.status_code == 422

    r = admin.post(USUARIOS, json=base)
    assert r.status_code == 201, r.text
    temporal = r.json()["contrasena_temporal"]
    assert len(temporal) == 16 and r.json()["usuario"]["contrasena_temporal"] is True
    assert "hash" not in r.text
    assert admin.post(USUARIOS, json=base).status_code == 409

    c, _ = reloj_movil
    ingreso = ingresar(c, "mquispe.gdur", temporal)
    assert ingreso.status_code == 200 and ingreso.json()["contrasena_temporal"] is True
    alta = sesion.scalar(select(Bitacora).where(Bitacora.accion == "ALTA_USUARIO")
                         .order_by(Bitacora.id_bitacora.desc()).limit(1))
    assert alta.recurso_id == r.json()["usuario"]["id_usuario"]
    assert temporal not in str(alta.detalle)


def test_cpi33_cambio_de_rol_cierra_las_sesiones_del_usuario(como, reloj_movil,
                                                             nuevo_usuario):
    c, _ = reloj_movil
    nombre, contrasena, id_usuario = nuevo_usuario("AU", "GDUR")
    ingresar(c, nombre, contrasena)
    assert c.get(INICIO).status_code == 200
    r = como("ADM").put(f"{USUARIOS}/{id_usuario}", json={
        "nombres_apellidos": "Usuario de prueba", "codigo_rol": "GA", "unidad_sigla": "GA"})
    assert r.status_code == 200 and r.json()["rol"]["codigo"] == "GA"
    assert c.get(INICIO).status_code == 401  # el nuevo permiso rige desde el siguiente ingreso
    assert ingresar(c, nombre, contrasena).json()["rol"]["codigo"] == "GA"


def test_cpi34_restablecer_desbloquea_y_entrega_nueva_temporal(como, reloj_movil,
                                                               nuevo_usuario):
    c, _ = reloj_movil
    nombre, contrasena, id_usuario = nuevo_usuario()
    for intento in range(3):
        ingresar(c, nombre, f"incorrecta-{intento}")
    admin = como("ADM")
    fila = next(u for u in admin.get(USUARIOS, params={"buscar": nombre}).json())
    assert fila["bloqueado"] is True

    r = admin.post(f"{USUARIOS}/{id_usuario}/restablecimiento")
    assert r.status_code == 200 and r.json()["usuario"]["bloqueado"] is False
    assert ingresar(c, nombre, contrasena).status_code == 401
    assert ingresar(c, nombre, r.json()["contrasena_temporal"]).json()[
        "contrasena_temporal"] is True


def test_cpi35_baja_logica_seudonimiza_y_cierra_sesiones(como, reloj_movil, nuevo_usuario,
                                                         credenciales, sesion):
    c, _ = reloj_movil
    nombre, contrasena, id_usuario = nuevo_usuario("JL", "SGASG")
    ingresar(c, nombre, contrasena)
    admin = como("ADM")
    r = admin.post(f"{USUARIOS}/{id_usuario}/baja")
    assert r.status_code == 200
    assert r.json()["estado"] == "BAJA" and r.json()["nombre_usuario"] == f"baja-{id_usuario}"
    assert r.json()["nombres_apellidos"] == "Usuario dado de baja"
    assert c.get(INICIO).status_code == 401
    assert ingresar(c, nombre, contrasena).status_code == 401
    assert admin.post(f"{USUARIOS}/{id_usuario}/baja").status_code == 409

    yo = admin.get("/api/v1/auth/yo").json()
    assert admin.post(f"{USUARIOS}/{yo['id_usuario']}/baja").status_code == 409
    propia = admin.put(f"{USUARIOS}/{yo['id_usuario']}", json={
        "nombres_apellidos": "Admin", "codigo_rol": "GA", "unidad_sigla": "GA"})
    assert propia.status_code == 409
    assert admin.post(f"{USUARIOS}/{yo['id_usuario']}/restablecimiento").status_code == 409


def test_cpi36_inicio_muestra_tarjetas_y_pendientes_solo_al_area_usuaria(como, cuerpo_base):
    au = como("AU")
    assert au.post("/api/v1/requerimientos", json=cuerpo_base).status_code == 201
    inicio = au.get(INICIO).json()
    assert inicio["pendientes_disponibles"] is True
    assert inicio["fecha_corte_mef"] is not None
    tarjetas = inicio["tarjetas"]
    assert tarjetas["verde"] + tarjetas["ambar"] + tarjetas["rojo"] >= 1
    assert any(p["accion"] == "Completar paso 2" for p in inicio["pendientes"])

    ga = como("GA").get(INICIO).json()
    assert ga["pendientes_disponibles"] is True and ga["tarjetas"] is None
    jl = como("JL").get(INICIO).json()  # sus pendientes salen de P09, P10 y P13 (parte 3B)
    assert jl["pendientes_disponibles"] is True and jl["tarjetas"] is None
    assert como("ADM").get(INICIO).json()["pendientes_disponibles"] is False
