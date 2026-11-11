# Sistema presupuestal de validación previa

Proyecto de Fin de Carrera 05 — Escuela Profesional de Ingeniería de Sistemas, UCSM.
*Optimización del proceso de contratación de bienes y servicios por montos iguales o inferiores a 8 UIT en la Municipalidad de Uchumayo.*

Autores: Rodrigo Mijael Arenas Ichocan y Piero Anthony Cahuana Cabrera. Asesor: Ing. Néstor Torres.

## Arquitectura

Arquitectura en capas con separación cliente-servidor (Práctica 5):

| Capa | Carpeta | Tecnología |
|---|---|---|
| Presentación | `frontend/` | Astro + React + Tailwind |
| Seguridad (transversal) | `backend/app/seguridad/` | FastAPI |
| Frontera de la API | `backend/app/api/v1/`, `backend/app/esquemas/` | FastAPI + Pydantic |
| Lógica de negocio | `backend/app/servicios/` | Python |
| Acceso a datos | `backend/app/repositorios/`, `backend/app/modelos/` | SQLAlchemy |
| Datos | `backend/migraciones/` | PostgreSQL 17.6 (Alembic) |
| Extracción | `backend/app/extraccion/` | Python (programado) |

## Ambientes

| Ambiente | Rama | Base de datos | Datos |
|---|---|---|---|
| Desarrollo | `feat/*` | PostgreSQL 17.6 local (`docker-compose.dev.yml`) | Mock (semillas) |
| Calidad | `calidad` | Proyecto Supabase de calidad | No reales, completos |
| Producción | `main` | Proyecto Supabase de producción | Versión validada por el usuario |

Flujo: desarrollo → calidad → producción. Convenciones en [`docs/convenciones.md`](docs/convenciones.md).

## Ejecutar en desarrollo

```bash
docker compose -f docker-compose.dev.yml up -d          # PostgreSQL 17.6 local
cd backend
python -m venv .venv && .venv\Scripts\activate          # Windows (en Linux/macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt
copy .env.example .env                                   # Windows (en Linux/macOS: cp)
alembic upgrade head                                     # crea las 23 tablas
python -m semillas.cargar                                # catálogos, regla y datos mock
python -m semillas.usuarios                              # un usuario por rol (contraseñas temporales)
uvicorn app.main:app --reload                            # http://localhost:8000/docs
```

`semillas.usuarios` imprime una sola vez la contraseña temporal de cada usuario de prueba
(`admin`, `au.gdur`, `au.gsp`, `gerencia`, `logistica`, `presupuesto`); en el primer ingreso el
sistema obliga a cambiarla. El repositorio es público y no contiene ninguna contraseña.

Pruebas (las de integración necesitan una base vacía propia):

```bash
docker exec svp_db_dev createdb -U svp svp_test
set TEST_DATABASE_URL=postgresql+psycopg://svp:svp_dev_local@localhost:5432/svp_test   # PowerShell: $env:TEST_DATABASE_URL="..."
pytest --cov
ruff check .
```
