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
| Datos | `backend/migraciones/` | PostgreSQL 17.6 |
| Extracción | `backend/app/extraccion/` | Python (programado) |

## Ambientes

| Ambiente | Rama | Base de datos | Datos |
|---|---|---|---|
| Desarrollo | `feat/*` | PostgreSQL 17.6 local (`docker-compose.dev.yml`) | Mock (semillas) |
| Calidad | `calidad` | Proyecto Supabase de calidad | No reales, completos |
| Producción | `main` | Proyecto Supabase de producción | Versión validada por el usuario |

Flujo: desarrollo → calidad → producción. Convenciones en [`docs/convenciones.md`](docs/convenciones.md).
