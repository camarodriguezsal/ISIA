# Research & Technical Decisions: Resumen de Incidentes Activos (Hito 002)

**Branch**: `002-active-incidents-summary` | **Date**: 2026-11-23

## 1. Diseño del Puerto Secundario (`IncidentRepositoryPort`)

- **Decision**: Definir `IncidentRepositoryPort` en `src/application/ports.py` usando `typing.Protocol` decorado con `@runtime_checkable` e incluyendo los 5 métodos requeridos: `save_incident`, `get_incident`, `find_open_duplicates`, `list_active_incidents` y `check_health`.
- **Rationale**: El tipado estructural (`Protocol`) evita acoplar los adaptadores por herencia nominal, mantiene `src/application/` con cero dependencias externas y permite verificar en pruebas unitarias (`isinstance(repo, IncidentRepositoryPort)`) que `SQLiteIncidentRepository` cumple el contrato.
- **Alternatives considered**: `abc.ABC` con herencia explícita (rechazado por la Constitución §II y `ADR-003`, que especifican `typing.Protocol`).

## 2. Extracción y Optimización de Persistencia SQLite

- **Decision**: Implementar `SQLiteIncidentRepository` en `src/adapters/outbound/sqlite_repository.py` usando `sqlite3` de la librería estándar, con:
  - Índice compuesto `CREATE INDEX IF NOT EXISTS idx_incidents_component_status ON incidents (component, status)`.
  - Consulta única parametrizada con `INNER JOIN sla_policies p ON i.severity = p.severity` y filtrado en SQL (`WHERE i.status IN ('OPEN', 'IN_PROGRESS')` y opcionalmente `AND i.component = ?`), orden determinista (`ORDER BY i.created_at ASC, i.incident_id ASC`).
  - `check_same_thread=False` en `sqlite3.connect(...)` para compatibilidad segura con el pool de hilos de FastAPI / `TestClient`.
- **Rationale**: Elimina el escaneo completo en memoria (`SELECT * FROM incidents`) y las consultas N+1 a `sla_policies` presentes en `src/incident_repository.py`, cumpliendo `ADR-001` y el objetivo de rendimiento `< 1s` (SC-003).
- **Alternatives considered**: SQLAlchemy ORM (prohibido por `ADR-001` y Constitución §III).

## 3. Fábrica de Repositorio (`DATABASE_URL`)

- **Decision**: Crear `src/adapters/outbound/factory.py` con `create_repository(database_url: Optional[str] = None) -> IncidentRepositoryPort` leyendo `os.getenv("DATABASE_URL", "sqlite:///:memory:")`.
  - `sqlite:///:memory:` -> `db_path = ":memory:"`
  - `sqlite:///ruta/relativa.db` -> `db_path = "ruta/relativa.db"`
  - `sqlite:////ruta/absoluta.db` -> `db_path = "/ruta/absoluta.db"`
  - Esquemas no soportados -> `ValueError` descriptivo.
- **Rationale**: Centraliza la selección del adaptador de persistencia en el *composition root* (Constitución §II) y permite que `src/adapters/inbound/` nunca importe `SQLiteIncidentRepository` directamente.
- **Alternatives considered**: Instanciar `SQLiteIncidentRepository` directamente en `app.py` y `cli.py` (rechazado: viola la frontera `inbound -> outbound.factory`).

## 4. Orquestación en `IncidentService` y Modelos de Resumen

- **Decision**:
  - `IncidentService.__init__(self, repository: Optional[IncidentRepositoryPort] = None)` mantiene compatibilidad hacia atrás con `triage_incident` (que es stateless) y requiere un repositorio configurado al invocar `get_active_incidents_summary`.
  - Definir dataclasses puros en `src/application/services.py` (o `src/domain/models.py` si son de lectura del dominio): `ActiveIncidentSummaryItem` y `ActiveIncidentsSummary` (con `total_active`, `breached_count`, `incidents`).
  - Validar `component_filter`: si se proporciona (`is not None`) y `component_filter.strip() == ""`, lanzar `ValidationError`.
  - Si `reference_time` es `None`, usar `datetime.now()`.
  - Evaluar cada incidente retornado por `repository.list_active_incidents(component_filter=...)` con `evaluate_sla_status(incident, reference_time=effective_ref_time)` de `src/domain/sla_calculator.py`.
- **Rationale**: Garantiza una única fuente de verdad para el cálculo de SLA, escalamiento y validación de negocio, logrando 100% de paridad entre HTTP y CLI (SC-001, SC-002).
- **Alternatives considered**: Calcular `elapsed_minutes` en SQL (prohibido por Constitución §I: la lógica de horario hábil `P2`/`P3` pertenece exclusivamente a `src/domain/sla_calculator.py`).

## 5. Verificación Estática de Fronteras Hexagonales con Ruff

- **Decision**:
  - En `pyproject.toml`:
    - `[tool.ruff.lint]` con `select = ["E4", "E7", "E9", "F", "TID"]`.
    - `[tool.ruff.lint.flake8-tidy-imports]` con `ban-relative-imports = "parents"`.
  - Archivos jerárquicos por capa con `extend` hacia `pyproject.toml`:
    - `src/domain/ruff.toml` (`extend = "../../pyproject.toml"`): `TID251` prohíbe `fastapi`, `pydantic`, `typer`, `uvicorn`, `sqlite3`, `sqlalchemy`, `src.application`, `src.adapters`.
    - `src/application/ruff.toml` (`extend = "../../pyproject.toml"`): `TID251` prohíbe `fastapi`, `pydantic`, `typer`, `uvicorn`, `sqlite3`, `sqlalchemy`, `src.adapters`.
    - `src/adapters/inbound/ruff.toml` (`extend = "../../../pyproject.toml"`): `TID251` prohíbe `sqlite3`, `sqlalchemy` y `src.adapters.outbound.sqlite_repository` (permitiendo únicamente `src.adapters.outbound.factory`).
- **Rationale**: Cumple la skill `hexagonal-architecture` y la Constitución §IV, haciendo que `uv run ruff check src/` falle inmediatamente ante cualquier violación de frontera.
- **Alternatives considered**: Revisiones manuales o scripts AST ad-hoc (menos integrados y más costosos de mantener que Ruff nativo).
