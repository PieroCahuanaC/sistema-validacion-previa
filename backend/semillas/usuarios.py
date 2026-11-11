"""Crea un usuario por rol para probar el sistema (ambientes de desarrollo y calidad).

Uso:  python -m semillas.usuarios            crea los que falten
      python -m semillas.usuarios --restablecer   vuelve a generar todas las contraseñas

Las contraseñas son temporales, aleatorias y se imprimen UNA SOLA VEZ en la consola: el
repositorio es público y no contiene ninguna contraseña. En el primer ingreso cada usuario
debe cambiarla (CU-09). Los nombres son ficticios (Ley N.° 29733).
"""

import argparse

from sqlalchemy import select

from app.core.db import FabricaSesion
from app.modelos.catalogos import Rol, UnidadOrganica
from app.modelos.seguridad import Usuario
from app.seguridad import contrasenas

# (nombre de usuario, nombres ficticios, rol, sigla de la unidad orgánica)
USUARIOS_DE_PRUEBA = [
    ("admin", "Administrador del sistema (prueba)", "ADM", None),
    ("au.gdur", "Área Usuaria GDUR (prueba)", "AU", "GDUR"),
    ("au.gsp", "Área Usuaria GSP (prueba)", "AU", "GSP"),
    ("gerencia", "Gerencia de Administración (prueba)", "GA", "GA"),
    ("logistica", "Jefe de Logística y Abastecimientos (prueba)", "JL", "SGASG"),
    ("presupuesto", "Jefe de Presupuesto (prueba)", "JP", "OPP"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restablecer", action="store_true")
    args = parser.parse_args()
    with FabricaSesion() as sesion:
        roles = {r.codigo: r.id_rol for r in sesion.scalars(select(Rol))}
        unidades = {u.sigla: u.id_unidad for u in sesion.scalars(select(UnidadOrganica))}
        if not roles:
            raise SystemExit("Faltan los catálogos: ejecute primero python -m semillas.cargar")
        print("Contraseñas temporales (anótelas ahora; no se vuelven a mostrar):")
        for nombre, nombres, rol, sigla in USUARIOS_DE_PRUEBA:
            usuario = sesion.scalar(select(Usuario).where(Usuario.nombre_usuario == nombre))
            if usuario is not None and not args.restablecer:
                print(f"  {nombre:<12} ya existe (use --restablecer para una nueva contraseña)")
                continue
            temporal = contrasenas.generar_temporal()
            if usuario is None:
                usuario = Usuario(nombre_usuario=nombre, nombres_apellidos=nombres,
                                  id_rol=roles[rol], id_unidad=unidades.get(sigla),
                                  estado="ACTIVO", intentos_fallidos=0)
                sesion.add(usuario)
            usuario.hash_contrasena = contrasenas.hashear(temporal)
            usuario.contrasena_temporal = True
            usuario.intentos_fallidos = 0
            usuario.bloqueado_hasta = None
            print(f"  {nombre:<12} {rol:<4} {temporal}")
        sesion.commit()


if __name__ == "__main__":
    main()
