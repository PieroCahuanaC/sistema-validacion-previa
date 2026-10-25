# Convención de codificación

Se adopta desde el primer commit y se verifica de forma automática con Ruff (Python) en el pipeline de integración continua.

## Nomenclatura

| Elemento | Convención | Ejemplo |
|---|---|---|
| Idioma de los identificadores | Español, igual que el diccionario de datos de la Práctica 6 | `monto_estimado`, `saldo_meta` |
| Variables, funciones y módulos Python | `snake_case` (PEP 8) | `calcular_semaforo()` |
| Clases Python | `PascalCase` | `ReglaSemaforo` |
| Constantes | `MAYUSCULAS_CON_GUION` | `MOTIVO_SIN_DATOS_META` |
| Componentes React | `PascalCase.tsx`, un componente por archivo | `SemaforoIndicador.tsx` |
| Variables y funciones TypeScript | `camelCase` | `registrarRequerimiento()` |
| Tablas y columnas SQL | `snake_case`, singular, como en la Práctica 6 | `requerimiento_item.precio_unitario_ref` |
| Rutas de la API | `/api/v1/` + recurso en plural | `POST /api/v1/requerimientos` |
| Archivos de prueba | `test_<modulo>.py`; casos `test_<condicion>_<resultado>` | `test_saldo_insuficiente_devuelve_rojo` |

## Estilo y comentarios

- Longitud máxima de línea: 100 caracteres. Indentación: 4 espacios en Python y 2 en TypeScript.
- Toda función pública lleva un *docstring* que indica qué hace y el RF o la regla de integridad (RI) que implementa.
- Los comentarios explican el **porqué** de una decisión, no repiten lo que dice el código.
- Tipado obligatorio en las firmas de funciones Python (type hints).
- Ningún secreto en el código: credenciales y cadenas de conexión se leen de variables de entorno (`.env`, no versionado).

## Principios SOLID y código limpio

| Principio | Cómo se aplica |
|---|---|
| Responsabilidad única (S) | Cada capa y cada módulo tiene una responsabilidad: los endpoints solo validan la entrada y delegan; la regla del semáforo no accede a la base de datos. |
| Abierto/cerrado (O) | La regla del semáforo es una cadena de reglas: agregar un motivo nuevo no modifica las reglas existentes. |
| Sustitución de Liskov (L) | Los adaptadores MEF, SEACE y CSV implementan la misma interfaz de carga y son intercambiables. |
| Segregación de interfaces (I) | Los repositorios exponen solo las operaciones que usa cada servicio. |
| Inversión de dependencias (D) | Los servicios reciben sus repositorios y el usuario actual por inyección de dependencias de FastAPI, lo que permite probarlos con dobles (mocks). |

## Control de versiones

- Ramas: `main` (producción), `calidad` (ambiente de calidad) y `feat/<modulo>-<tema>` para cada tarea.
- Flujo: `feat/*` → *pull request* a `calidad` → *pull request* a `main`. Las pruebas se ejecutan en cada *push* y en cada *pull request*.
- Commits pequeños, con formato *Conventional Commits* en español:

```
<tipo>(<ámbito>): <descripción en imperativo>
```

| Tipo | Uso |
|---|---|
| `feat` | Funcionalidad nueva |
| `fix` | Corrección de un defecto |
| `test` | Pruebas |
| `refactor` | Cambio interno sin cambiar el comportamiento |
| `docs` | Documentación |
| `chore` | Configuración, dependencias, estructura |
| `ci` | Pipeline de integración continua |

Ejemplo: `feat(validacion): agrega cadena de reglas del semáforo presupuestal`.
