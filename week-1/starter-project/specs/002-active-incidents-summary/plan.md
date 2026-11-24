# Implementation Plan: Resumen de Incidentes Activos (Hito 002)

**Branch**: `002-active-incidents-summary` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-active-incidents-summary/spec.md`

## Summary

Implementar la consulta de resumen de incidentes activos (`OPEN` e `IN_PROGRESS`) con paridad total entre HTTP (`GET /api/v1/incidents/summary`) y CLI (`summary [--component ...] [--reference-time ...]`), aplicando estrictamente la Arquitectura Hexagonal (`ADR-003`) y la Constitución de IncidentOps:

- **Puerto de salida (`src/application/ports.py`)**: Definir `IncidentRepositoryPort` (`typing.Protocol`, `@runtime_checkable`) con `save_incident`, `get_incident`, `find_open_duplicates`, `list_active_incidents` y `check_health`.
- **Adaptador secundario SQLite y fábrica (`src/adapters/outbound/sqlite_repository.py`, `src/adapters/outbound/factory.py`)**: Extraer y optimizar la persistencia heredada de `src/incident_repository.py` usando `INNER JOIN sla_policies`, filtrado en SQL (`status IN ('OPEN', 'IN_PROGRESS')` y `component = ?` opcional), índice compuesto `idx_incidents_component_status ON incidents(component, status)` y selección de repositorio desde `DATABASE_URL` (default `sqlite:///:memory:`).
- **Capa de aplicación (`src/application/services.py`)**: Inyectar `IncidentRepositoryPort` en `IncidentService` y agregar `get_active_incidents_summary(component_filter, reference_time)` delegando el cálculo de SLA y escalamiento exclusivamente a `src/domain/sla_calculator.py`.
- **Adaptadores primarios (`src/adapters/inbound/`)**: Exponer `ActiveIncidentItem`, `ActiveIncidentsSummaryResponse` y `GET /api/v1/incidents/summary` en FastAPI, más el subcomando `summary` en Typer, ambos conectados al *composition root* mediante `src.adapters.outbound.factory`.
- **Gobernanza estática con Ruff**: Configurar `[tool.ruff.lint]` (`select = ["E4", "E7", "E9", "F", "TID"]`) y `ban-relative-imports = "parents"` en `pyproject.toml`, más archivos jerárquicos `src/domain/ruff.toml`, `src/application/ruff.toml` y `src/adapters/inbound/ruff.toml` con `extend` hacia `pyproject.toml` y reglas `TID251` (`banned-api`).
- **Pruebas BDD y de contrato (`tests/test_spec_002_summary.py`)**: Cubrir los 4 escenarios BDD (resumen global excluyendo `RESOLVED`, filtro por componente, estado vacío, paridad CLI), casos borde de validación (`component` en blanco, `reference_time` inválido, umbral preventivo 75%, horario hábil `P2`/`P3`) y cumplimiento estructural de `IncidentRepositoryPort` sobre `SQLiteIncidentRepository`.

## Technical Context

**Language/Version**: Python `>=3.10` gestionado con `uv` (`pyproject.toml`, `uv.lock`)

**Primary Dependencies**: `fastapi>=0.115.0`, `uvicorn>=0.32.0`, `pydantic>=2.9.0`, `typer>=0.12.0` (adaptadores primarios); librería estándar `sqlite3` (adaptador secundario); `pytest>=8.3.0`, `httpx>=0.27.0`, `ruff>=0.17.4` (desarrollo y verificación)

**Storage**: SQLite (`sqlite3` estándar, sin ORM según `ADR-001`), configurable vía `DATABASE_URL` (default `sqlite:///:memory:`)

**Testing**: `uv run pytest -v` (`fastapi.testclient.TestClient`, `typer.testing.CliRunner`) + `uv run ruff check src/`

**Target Platform**: Servicio HTTP local/servidor Linux/macOS + CLI multiplataforma

**Project Type**: Web service + CLI bajo Arquitectura Hexagonal (`src/domain`, `src/application`, `src/adapters/{inbound,outbound}`)

**Performance Goals**: Respuesta `< 1s` para consultas de resumen sobre cargas operativas típicas (10,000+ incidentes), eliminando escaneos completos en memoria y consultas N+1

**Constraints**: Cero dependencias externas en `src/domain/` y `src/application/`; `src/adapters/inbound/` solo puede importar `src.adapters.outbound.factory` desde `outbound`; validación determinista de fronteras con `uv run ruff check src/`

**Scale/Scope**: Hito 002 — 1 nuevo puerto, 1 adaptador SQLite optimizado + factory, 1 nuevo caso de uso en `IncidentService`, 1 endpoint REST, 1 comando CLI, 4 archivos de configuración Ruff y 1 suite de pruebas BDD/contrato

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / Compuerta | Estado | Verificación de Diseño |
| :--- | :--- | :--- |
| **I. Núcleo Determinista Único (`src/domain/`)** | PASS | El cálculo de `elapsed_minutes`, `is_breached` y `requires_escalation` se delega exclusivamente a `src/domain/sla_calculator.py` (`evaluate_sla_status`). No se duplica lógica de SLA en SQL, FastAPI ni Typer. |
| **II. Arquitectura Hexagonal Estricta (`ADR-003`)** | PASS | `IncidentRepositoryPort` (`Protocol`) vive en `src/application/ports.py`; `SQLiteIncidentRepository` vive en `src/adapters/outbound/sqlite_repository.py`; la selección ocurre en `src/adapters/outbound/factory.py` usando `DATABASE_URL`. |
| **III. Gobernanza Técnica y Stack Aprobado** | PASS | Se mantiene el stack aprobado (`FastAPI`, `Pydantic v2`, `Typer`, `sqlite3` estándar sin ORM, `uv`, `pytest`, `ruff`). Sin nuevas dependencias externas. |
| **IV. Verificación Estática y Pruebas BDD Obligatorias** | PASS | Se incorporan reglas Ruff (`TID251`/`TID252`) jerárquicas por capa ejecutables con `uv run ruff check src/` y pruebas BDD en `tests/test_spec_002_summary.py` ejecutables con `uv run pytest -v`. |

**Post-Phase 1 Re-check**: PASS — El modelo de datos (`data-model.md`) y los contratos HTTP/CLI (`contracts/http-api.md`, `contracts/cli.md`) mantienen paridad exacta y cero filtración de detalles de transporte o SQL hacia `domain`/`application`.

## Project Structure

### Documentation (this feature)

```text
specs/002-active-incidents-summary/
├── plan.md              # Este documento (/speckit.plan)
├── research.md          # Decisiones técnicas y diseño de fronteras (Phase 0)
├── data-model.md        # Entidades, puerto, esquema SQLite e índices (Phase 1)
├── quickstart.md        # Guía de validación end-to-end (Phase 1)
├── contracts/           # Contratos HTTP y CLI (Phase 1)
│   ├── http-api.md
│   └── cli.md
└── tasks.md             # Pendiente (/speckit.tasks)
```

### Source Code (repository root)

```text
pyproject.toml                           # [tool.ruff.lint] base + ban-relative-imports = "parents"
src/
├── domain/
│   ├── ruff.toml                        # Extiende ../../pyproject.toml; prohíbe frameworks, BD, application, adapters
│   ├── models.py                        # Entidades puras (Incident, SLAEvaluation, etc.)
│   ├── sla_calculator.py                # Fuente única de cálculo SLA y escalamiento
│   └── triage_rules.py                  # Motor determinista de triaje
├── application/
│   ├── ruff.toml                        # Extiende ../../pyproject.toml; prohíbe frameworks, BD, adapters
│   ├── ports.py                         # IncidentRepositoryPort (Protocol @runtime_checkable)
│   └── services.py                      # IncidentService (+ get_active_incidents_summary)
└── adapters/
    ├── inbound/
    │   ├── ruff.toml                    # Extiende ../../../pyproject.toml; prohíbe sqlite3 y repos concretos
    │   ├── cli.py                       # Typer: triage + summary [--component] [--reference-time]
    │   └── api/
    │       ├── schemas.py               # Pydantic v2: + ActiveIncidentItem, ActiveIncidentsSummaryResponse
    │       └── app.py                   # FastAPI: + GET /api/v1/incidents/summary
    └── outbound/
        ├── __init__.py
        ├── sqlite_repository.py         # SQLiteIncidentRepository (INNER JOIN + índice compuesto)
        └── factory.py                   # create_repository(database_url) desde DATABASE_URL

tests/
├── conftest.py                          # Fixtures compartidos (TestClient, CliRunner, repo SQLite)
├── test_spec_001_triage.py              # Regresión Hito 001
└── test_spec_002_summary.py             # Escenarios BDD + contrato IncidentRepositoryPort
```

**Structure Decision**: Se adopta la estructura hexagonal existente en `src/` completando la capa `src/adapters/outbound/` y el archivo `src/application/ports.py`, junto con la configuración jerárquica de Ruff por capa para garantizar el cumplimiento automático de `ADR-003`.

## Complexity Tracking

> Sin violaciones a la Constitución. No se requieren excepciones.
