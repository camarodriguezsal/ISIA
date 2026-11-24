---
name: hexagonal-architecture
description: Enforce IncidentOps Hexagonal Architecture (ADR-003) layer import boundaries, REST/CLI adapter parity, and Ruff static boundary checks (`TID251`/`TID252`).
---

# Hexagonal Architecture — IncidentOps (`ADR-003`)

Usa esta skill siempre que diseñes, implementes o revises módulos en `src/` para garantizar el cumplimiento estricto de **Puertos y Adaptadores** (`adapters -> application -> domain`).

## 1. Reglas de Importación por Capa

| Capa | Ruta | Imports permitidos | Imports prohibidos |
| :--- | :--- | :--- | :--- |
| **Dominio** | `src/domain/` | Exclusivamente librería estándar de Python y módulos internos de `src.domain`. | Frameworks web/CLI (`fastapi`, `pydantic`, `typer`, `uvicorn`), drivers de BD (`sqlite3`, `psycopg`, `sqlalchemy`), ORMs, I/O de transporte, `src.application`, `src.adapters`. |
| **Aplicación** | `src/application/` | Librería estándar de Python (`typing.Protocol`, etc.) y `src.domain`. | Frameworks web/CLI, drivers de BD, ORMs, `src.adapters`. |
| **Adaptadores Primarios** | `src/adapters/inbound/` | `src.application`, `src.domain`, `src.adapters.outbound.factory` (solo en el *composition root*), `fastapi`, `pydantic`, `typer`. | Drivers de BD (`sqlite3`, etc.) y repositorios concretos de `src.adapters.outbound.*` (salvo `factory`). |
| **Adaptadores Secundarios** | `src/adapters/outbound/` | `src.application.ports` (`IncidentRepositoryPort`), `src.domain`, drivers de BD aprobados (`sqlite3` estándar según `ADR-001`). | `src.adapters.inbound`, frameworks web/CLI (`fastapi`, `typer`). |

### Responsabilidades clave
- **`src/domain/`**: Núcleo determinista único (`models.py`, `triage_rules.py`, `sla_calculator.py`). Sin efectos secundarios ni dependencias externas.
- **`src/application/`**: Define `IncidentRepositoryPort` (`typing.Protocol`) en `ports.py` y orquesta casos de uso en `IncidentService` (`services.py`).
- **`src/adapters/inbound/`**: Traduce entradas/salidas HTTP o CLI y delega **siempre** la ejecución en `IncidentService`. Nunca instancia repositorios concretos directamente; obtiene la implementación vía `src.adapters.outbound.factory` (configurada con `DATABASE_URL`).
- **`src/adapters/outbound/`**: Implementa `IncidentRepositoryPort` de forma intercambiable.

## 2. Paridad entre Adaptadores Primarios (REST y CLI)

- Todo caso de uso expuesto en **REST** (`FastAPI`) y **CLI** (`Typer`) debe invocar exactamente el **mismo método** de `IncidentService`.
- Las reglas de validación de negocio, clasificación de severidad, cálculo de SLA, escalamiento y detección de duplicados **nunca** se duplican en endpoints ni comandos CLI.
- Mantener la capa de aplicación agnóstica al transporte garantiza que un futuro adaptador **MCP** pueda conectarse reutilizando el mismo `IncidentService`.

## 3. Validación Estática de Fronteras con Ruff

Las fronteras hexagonales se verifican estáticamente con **Ruff** usando `TID251` (`banned-api`) y `TID252` (`ban-relative-imports = "parents"`):

1. **Configuración base en `pyproject.toml`**:
   ```toml
   [tool.ruff.lint]
   select = ["E4", "E7", "E9", "F", "TID"]

   [tool.ruff.lint.flake8-tidy-imports]
   ban-relative-imports = "parents"
   ```
2. **Archivos jerárquicos `ruff.toml` por capa** (cada uno extiende `../../pyproject.toml` o `../../../pyproject.toml` y declara `[lint.flake8-tidy-imports.banned-api]`):
   - `src/domain/ruff.toml`: prohíbe `fastapi`, `pydantic`, `typer`, `uvicorn`, `sqlite3`, `sqlalchemy`, `src.application`, `src.adapters`.
   - `src/application/ruff.toml`: prohíbe `fastapi`, `pydantic`, `typer`, `uvicorn`, `sqlite3`, `sqlalchemy`, `src.adapters`.
   - `src/adapters/inbound/ruff.toml`: prohíbe `sqlite3`, `sqlalchemy` e imports directos a repositorios concretos de `src.adapters.outbound` (permitiendo únicamente `src.adapters.outbound.factory`).
3. **Verificación obligatoria antes de finalizar cualquier cambio**:
   ```bash
   uv run ruff check src/
   ```

