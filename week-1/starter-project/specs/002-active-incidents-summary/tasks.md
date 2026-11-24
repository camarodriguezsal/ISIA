# Tasks: Resumen de Incidentes Activos (Hito 002)

**Input**: Design documents from `/specs/002-active-incidents-summary/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/http-api.md](contracts/http-api.md), [contracts/cli.md](contracts/cli.md), [quickstart.md](quickstart.md)

**Tests**: Incluidos obligatoriamente conforme a la Constitución §IV (escenarios BDD y verificación de cumplimiento de `IncidentRepositoryPort` sobre `SQLiteIncidentRepository`).

**Organization**: Tareas agrupadas por fase y por historia de usuario (`US1`, `US2`, `US3`) para habilitar implementación y verificación incremental.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: Historia de usuario asociada (`[US1]`, `[US2]`, `[US3]`)
- Todas las tareas incluyen rutas exactas desde la raíz del proyecto (`week-1/starter-project/`).

---

## Phase 1: Setup (Gobernanza Estática de Fronteras con Ruff)

**Purpose**: Configurar Ruff con reglas `TID251` y `TID252` para validar automáticamente las fronteras hexagonales desde el inicio.

- [x] T001 Configure `[tool.ruff.lint]` with `select = ["E4", "E7", "E9", "F", "TID"]` and `[tool.ruff.lint.flake8-tidy-imports]` with `ban-relative-imports = "parents"` in `pyproject.toml`
- [x] T002 [P] Create domain layer Ruff rules extending `../../pyproject.toml` and banning `fastapi`, `pydantic`, `typer`, `uvicorn`, `sqlite3`, `sqlalchemy`, `src.application`, `src.adapters` in `src/domain/ruff.toml`
- [x] T003 [P] Create application layer Ruff rules extending `../../pyproject.toml` and banning `fastapi`, `pydantic`, `typer`, `uvicorn`, `sqlite3`, `sqlalchemy`, `src.adapters` in `src/application/ruff.toml`
- [x] T004 [P] Create inbound adapter layer Ruff rules extending `../../../pyproject.toml` and banning `sqlite3`, `sqlalchemy`, `src.adapters.outbound.sqlite_repository` in `src/adapters/inbound/ruff.toml`

---

## Phase 2: Foundational (Puerto Secundario, Repositorio SQLite, Factory y Servicio)

**Purpose**: Infraestructura hexagonal base bloqueante para todas las historias de usuario (`ports.py`, `sqlite_repository.py`, `factory.py`, `services.py`).

**⚠️ CRITICAL**: Ninguna historia de usuario puede comenzar hasta completar esta fase.

- [x] T005 Define `@runtime_checkable` `IncidentRepositoryPort(Protocol)` with `save_incident`, `get_incident`, `find_open_duplicates`, `list_active_incidents(component_filter: Optional[str] = None)`, and `check_health` in `src/application/ports.py`
- [x] T006 [P] Create outbound adapters package initializer in `src/adapters/outbound/__init__.py`
- [x] T007 Implement `SQLiteIncidentRepository` fulfilling `IncidentRepositoryPort` with `sla_policies` and `incidents` tables, composite index `idx_incidents_component_status ON incidents (component, status)`, `check_same_thread=False`, and optimized `INNER JOIN sla_policies` SQL query for `list_active_incidents` in `src/adapters/outbound/sqlite_repository.py`
- [x] T008 Implement `create_repository(database_url: Optional[str] = None) -> IncidentRepositoryPort` reading `DATABASE_URL` (default `sqlite:///:memory:`) and parsing `sqlite:///` URLs in `src/adapters/outbound/factory.py`
- [x] T009 Update `IncidentService` to accept optional `repository: Optional[IncidentRepositoryPort] = None`, define `ActiveIncidentSummaryItem` and `ActiveIncidentsSummary` frozen dataclasses, and implement `get_active_incidents_summary(component_filter: Optional[str] = None, reference_time: Optional[datetime] = None)` validating blank `component_filter` (`ValidationError`) and delegating SLA calculation to `evaluate_sla_status` from `src/domain/sla_calculator.py` in `src/application/services.py`

**Checkpoint**: Núcleo hexagonal, puerto, persistencia SQLite optimizada y caso de uso compartidos listos.

---

## Phase 3: User Story 1 - Consultar el resumen global de incidentes activos vía HTTP (Priority: P1) 🎯 MVP

**Goal**: Exponer `GET /api/v1/incidents/summary` devolviendo `total_active`, `breached_count` e `incidents` para todos los incidentes activos (`OPEN` e `IN_PROGRESS`), excluyendo `RESOLVED`.

**Independent Test**: Registrar incidentes `OPEN`, `IN_PROGRESS` y `RESOLVED` en `SQLiteIncidentRepository`, consultar `GET /api/v1/incidents/summary?reference_time=...` vía `TestClient` y verificar `200 OK`, totales y campos evaluados de SLA.

### Implementation for User Story 1

- [x] T010 [P] [US1] Add `ActiveIncidentItem` and `ActiveIncidentsSummaryResponse` Pydantic v2 schemas (with `from_summary` factory method) in `src/adapters/inbound/api/schemas.py`
- [x] T011 [US1] Wire `create_repository()` in `create_app()` and add `GET /api/v1/incidents/summary` accepting optional `component` and `reference_time` query parameters (mapping `ValidationError` to HTTP `422`) in `src/adapters/inbound/api/app.py`

### Tests for User Story 1

- [x] T012 [US1] Create `tests/test_spec_002_summary.py` with contract test verifying `isinstance(repo, IncidentRepositoryPort)` on `SQLiteIncidentRepository` and BDD Scenario 1 (global summary excluding `RESOLVED`, SLA breach vs 75% preventive escalation threshold, and `P2`/`P3` business-hours SLA)

**Checkpoint**: User Story 1 (MVP) completamente funcional y verificable de forma independiente.

---

## Phase 4: User Story 2 - Filtrar el resumen por componente y manejar estado vacío (Priority: P2)

**Goal**: Garantizar filtrado exacto por `component`, respuesta `200 OK` vacía válida (`total_active=0`, `breached_count=0`, `incidents=[]`) y rechazo HTTP `422` ante `component` vacío/en blanco o `reference_time` inválido.

**Independent Test**: Consultar `GET /api/v1/incidents/summary?component=<nombre>` con coincidencias, sin coincidencias, sin datos activos y con parámetros inválidos vía `TestClient`.

### Tests for User Story 2

- [x] T013 [US2] Add BDD Scenario 2 (component filter `component=payments-gateway`), BDD Scenario 3 (empty state returning `200 OK` with `total_active=0`, `breached_count=0`, `incidents=[]`), and HTTP `422` validation edge cases (blank `component`, invalid `reference_time`) in `tests/test_spec_002_summary.py`

**Checkpoint**: User Stories 1 y 2 verificadas de forma independiente sobre HTTP.

---

## Phase 5: User Story 3 - Consultar el resumen equivalente desde la CLI (Priority: P3)

**Goal**: Exponer el subcomando Typer `summary [--component ...] [--reference-time ...]` con 100% de paridad JSON respecto a `GET /api/v1/incidents/summary`.

**Independent Test**: Ejecutar `summary` con `CliRunner` apuntando a la misma base SQLite vía `DATABASE_URL` y verificar salida JSON idéntica a HTTP, código `0` en éxito y código `1` ante errores de validación.

### Implementation for User Story 3

- [x] T014 [US3] Add Typer command `summary` with optional `--component` and `--reference-time` options using `create_repository()` and `IncidentService.get_active_incidents_summary()`, printing JSON to `stdout` (`exit 0`) and validation errors to `stderr` (`exit 1`) in `src/adapters/inbound/cli.py`

### Tests for User Story 3

- [x] T015 [US3] Add BDD Scenario 4 (CLI parity with HTTP using `CliRunner` and `DATABASE_URL` on a shared SQLite file, plus CLI validation edge cases for blank `--component` and invalid `--reference-time`) in `tests/test_spec_002_summary.py`

**Checkpoint**: Las 3 historias de usuario y los 4 escenarios BDD funcionan con paridad HTTP/CLI.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Limpieza de fixtures y verificación final de las compuertas de calidad de la Constitución.

- [x] T016 [P] Review and update shared test fixtures if needed (preserving compatibility with `tests/test_spec_001_triage.py`) in `tests/conftest.py`
- [x] T017 Run static boundary validation (`uv run ruff check src/`) and full BDD/unit test suite (`uv run pytest -v`) to verify all quality gates pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Sin dependencias; `T002`, `T003`, `T004` pueden ejecutarse en paralelo tras `T001`.
- **Phase 2 (Foundational)**: `T005` y `T006` inician en paralelo → `T007` y `T009` dependen de `T005` → `T008` depende de `T005` y `T007`. Bloquea las fases 3, 4 y 5.
- **Phase 3 (US1 - MVP)**: Depende de Phase 2 (`T010` → `T011` → `T012`).
- **Phase 4 (US2)**: Depende de `T011` y `T012` (`T013`).
- **Phase 5 (US3)**: Depende de Phase 2 (`T014` → `T015`); `T014` puede implementarse en paralelo con Phase 3/4.
- **Phase 6 (Polish)**: Depende de Phases 1–5 (`T016`, `T017`).

### Parallel Opportunities

```text
# Phase 1 en paralelo tras T001:
T002 (src/domain/ruff.toml) | T003 (src/application/ruff.toml) | T004 (src/adapters/inbound/ruff.toml)

# Phase 2 en paralelo tras T005:
T007 (src/adapters/outbound/sqlite_repository.py) | T009 (src/application/services.py)

# Adaptadores primarios en paralelo tras Phase 2:
T010 + T011 (HTTP FastAPI) | T014 (CLI Typer)
```

## Implementation Strategy

- **MVP First**: Completar Phases 1, 2 y 3 entrega el núcleo hexagonal completo, Ruff activo y `GET /api/v1/incidents/summary` probado.
- **Incremental Delivery**: Añadir Phase 4 (filtros/estado vacío/validaciones HTTP) y Phase 5 (paridad CLI), cerrando con Phase 6 (`uv run ruff check src/` y `uv run pytest -v`).
