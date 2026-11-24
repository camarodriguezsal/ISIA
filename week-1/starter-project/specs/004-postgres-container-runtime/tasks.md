# Tasks: Persistencia PostgreSQL, Chequeo Real de Salud y Runtime en Contenedores (Hito 004)

**Input**: Design documents from `/specs/004-postgres-container-runtime/`

**Prerequisites**: [spec.md](spec.md), [checklists/requirements.md](checklists/requirements.md), `docs/adr/004-persistencia-postgresql-y-runtime-contenedores.md` (`Aceptado`), `docs/constitution.md` (`v1.1.0`)

**Tests**: Incluidos obligatoriamente conforme a la Constitución (escenarios BDD 1–4, contrato `IncidentRepositoryPort` y portabilidad local sin Docker según `RNF-007`).

**Organization**: Tareas agrupadas por fase y por historia de usuario (`US1`–`US4`) para implementación y verificación incremental.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: Historia de usuario asociada (`[US1]`, `[US2]`, `[US3]`, `[US4]`)
- Todas las tareas incluyen rutas exactas desde la raíz del proyecto (`week-1/starter-project/`).

---

## Phase 1: Setup (Dependencias y Gobernanza Estática de Fronteras)

**Purpose**: Asegurar la dependencia `psycopg[binary]` y reforzar las reglas `TID251` de Ruff para prohibir `psycopg` y el adaptador concreto de PostgreSQL fuera de `src/adapters/outbound/`.

- [x] T001 Verify/add `psycopg[binary]` in `[project.dependencies]` in `pyproject.toml` and synced in `uv.lock`
- [x] T002 [P] Ban `psycopg` imports in `src/domain/ruff.toml` (`ADR-003`, `ADR-004`, `RNF-001`)
- [x] T003 [P] Ban `psycopg` imports in `src/application/ruff.toml` (`ADR-003`, `ADR-004`, `RNF-001`)
- [x] T004 [P] Ban `psycopg` and `src.adapters.outbound.postgres_repository` imports in `src/adapters/inbound/ruff.toml` (`ADR-003`, `ADR-004`, `RNF-001`)

---

## Phase 2: Foundational (Servicio de Salud, Adaptador PostgreSQL y Fábrica `DATABASE_URL`)

**Purpose**: Infraestructura hexagonal base bloqueante para todas las historias de usuario (`services.py`, `postgres_repository.py`, `factory.py`).

- [x] T005 Add `check_health(self) -> bool` in `IncidentService` delegating to `IncidentRepositoryPort.check_health()` (raising `RuntimeError` if `repository is None`) in `src/application/services.py` (`FR-001`)
- [x] T006 [P] Implement `PostgresIncidentRepository` fulfilling `IncidentRepositoryPort` using `psycopg` without ORM, explicit `%s`-parameterized SQL, idempotent DDL (`sla_policies`, `incidents`, indexes `idx_incidents_component_status` and `idx_incidents_dup_key`, `SLA_POLICY_TABLE` upsert), ISO-8601 `TEXT` timestamps, per-operation connections (`connect_timeout=3`), and real `SELECT 1` in `check_health()` catching `psycopg.Error` -> `False` in `src/adapters/outbound/postgres_repository.py` (`FR-005`–`FR-007`, `RNF-002`, `RNF-003`, `RNF-006`)
- [x] T007 Extend `create_repository(database_url: Optional[str] = None)` to select `PostgresIncidentRepository` for `postgresql://` / `postgres://`, `SQLiteIncidentRepository` for `sqlite:///` or unset (`sqlite:///:memory:`), and raise `ValueError` for empty or unsupported schemes in `src/adapters/outbound/factory.py` (`FR-008`)

---

## Phase 3: User Stories 1 & 2 - Chequeo Real de Salud HTTP/CLI (`200 OK` y `503 Service Unavailable`) (Priority: P1) 🎯 MVP

**Goal**: Exponer `GET /health` y comando CLI `health` ejecutando `SELECT 1` real, respondiendo `200`/`0` con `{"status": "ok", "database": "connected"}` o `503`/`1` con `{"status": "error", "database": "unavailable"}`.

- [x] T008 [P] [US1] [US2] Add `HealthResponse` Pydantic v2 schema (`status`, `database`) in `src/adapters/inbound/api/schemas.py`
- [x] T009 [US1] [US2] Expose `GET /health` returning `200 OK` or `503 Service Unavailable` via `JSONResponse` without leaking credentials in `src/adapters/inbound/api/app.py` (`FR-002`, `FR-003`, `RNF-005`, `RNF-006`)
- [x] T010 [P] [US1] [US2] Add Typer command `health` printing JSON payload to `stdout` with exit code `0` (connected) or `1` (unavailable) in `src/adapters/inbound/cli.py` (`FR-004`)
- [x] T011 [US1] [US2] Create `tests/test_spec_004_runtime.py` with BDD Scenario 1 (`GET /health` `200` + CLI `health` `0`, verifying real `SELECT 1`) and BDD Scenario 2 (`503` + CLI `1`, including `psycopg.OperationalError` without credential leakage)

---

## Phase 4: User Story 3 - Selección Transparente SQLite / PostgreSQL vía `DATABASE_URL` (Priority: P1)

**Goal**: Verificar selección transparente entre SQLite y PostgreSQL según `DATABASE_URL` y cumplimiento de `IncidentRepositoryPort` sin requerir Docker localmente.

- [x] T012 [US3] Add BDD Scenario 3 tests in `tests/test_spec_004_runtime.py` covering unset `DATABASE_URL` (`:memory:`), `sqlite:///...`, `postgresql://...`, `postgres://...`, `isinstance(..., IncidentRepositoryPort)` and `ValueError` on empty/unsupported schemes (`RNF-007`)

---

## Phase 5: User Story 4 - Orquestación Reproducible en 2 Contenedores (`api` + `db`) (Priority: P2)

**Goal**: Proveer `Dockerfile`, `.dockerignore` y `docker-compose.yml` reproducibles con `postgres:16-alpine`, volumen persistente, `pg_isready`, `depends_on: service_healthy` y healthcheck `/health` con `urllib.request`.

- [x] T013 [P] [US4] Create `Dockerfile` based on `python:3.12-slim` with `uv`, `uv.lock`, `--frozen --no-dev` and `uvicorn` on port `8000` (`FR-009`, `RNF-004`)
- [x] T014 [P] [US4] Create `.dockerignore` excluding `.venv/`, `.git/`, caches, local `.db` files and non-runtime directories (`FR-010`, `RNF-004`)
- [x] T015 [US4] Create `docker-compose.yml` with `db` (`postgres:16-alpine`, named volume `postgres_data`, `pg_isready`) and `api` (`DATABASE_URL` pointing to `db`, `depends_on: service_healthy`, `urllib.request` healthcheck against `/health`) (`FR-011`, `RNF-004`–`RNF-006`)
- [x] T016 [US4] Add BDD Scenario 4 contract tests for `Dockerfile`, `.dockerignore` and `docker-compose.yml` in `tests/test_spec_004_runtime.py`

---

## Phase 6: Polish & Verification Gates

**Purpose**: Actualizar documentación operativa y ejecutar las compuertas de calidad (`ruff` y `pytest`).

- [x] T017 [P] Update `docs/ROADMAP.md` reflecting completed milestones (`H001`–`H004`)
- [x] T018 Run static boundary validation (`uv run ruff check src/`) and full test suite (`uv run pytest -v`)
