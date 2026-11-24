# IncidentOps Constitution

Este documento constituye la Constitución oficial y normativa de **IncidentOps**. Establece los principios invariantes de dominio, arquitectura hexagonal y gobernanza técnica que toda especificación, plan de diseño, implementación y revisión debe cumplir.

## Core Principles

### I. Núcleo Determinista Único (`src/domain/`) — NON-NEGOTIABLE

Toda la lógica de negocio reside en una única fuente de verdad determinista dentro de `src/domain/` (`models.py`, `triage_rules.py`, `sla_calculator.py`) y **no puede duplicarse ni reinterpretarse** en adaptadores HTTP, comandos CLI, futuros servidores MCP ni consultas SQL:

- **Modelos y catálogos cerrados (`src/domain/models.py`)**:
  - Entidades y tipos puros: `Incident`, `SLARule`, `SLAEvaluation`, `TriageResult`.
  - **Severidades**: `P0`, `P1`, `P2`, `P3`.
  - **Estados (`IncidentStatus`)**: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`.
  - **Equipos válidos (`TeamName`)**: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`.
- **Reglas de triaje y enrutamiento (`src/domain/triage_rules.py`)**:
  - La clasificación de reportes (`classify_incident_report`) es determinista y evalúa impacto real, seguridad multi-tenant y radio de afectación, ignorando trampas léxicas aisladas (como `"hoy"`).
  - La clave de duplicados (`duplicate_group_key`) es generada exclusivamente por el dominio con formato estricto `<component>:<symptom_category>` para detección consistente de incidentes equivalentes.
- **Cálculo de SLA y escalamiento (`src/domain/sla_calculator.py`, `ADR-002`)**:
  - `SLA_POLICY_TABLE`:
    - `P0` (`60` min) y `P1` (`240` min): operación continua **24/7**.
    - `P2` (`480` min) y `P3` (`1440` min): **horario hábil Lunes a Viernes de 08:00 a 18:00** (600 min hábiles/día; fines de semana suman 0).
  - **Escalamiento preventivo y vencimiento**: `requires_escalation` permanece activo (`True`) siempre que el incidente no esté `RESOLVED` y haya alcanzado al menos el **75%** de su presupuesto de SLA (`escalation_threshold_ratio = 0.75`) o haya superado el límite (`is_breached = True`).

### II. Arquitectura Hexagonal Estricta (`ADR-003`) — NON-NEGOTIABLE

En cumplimiento de `docs/adr/003-arquitectura-hexagonal.md`, `src/` sigue **Puertos y Adaptadores** con inversión estricta de dependencias hacia el núcleo (`adapters -> application -> domain`):

- **`src/domain/` (Núcleo Puro)**: Exclusivamente librería estándar de Python. **Cero imports externos** (sin frameworks web, CLI, I/O de transporte ni drivers/ORMs de base de datos).
- **`src/application/` (Casos de Uso y Puertos)**:
  - `ports.py`: contratos de puertos secundarios definidos mediante tipado estructural (`typing.Protocol`).
  - `services.py`: orquestación compartida de casos de uso (`IncidentService`).
  - Agnóstico al transporte HTTP/CLI/MCP y al motor de almacenamiento concreto.
- **`src/adapters/inbound/` (Adaptadores Primarios)**:
  - Interfaces delgadas con **FastAPI** (REST) y **Typer** (CLI) que traducen entradas/salidas hacia `IncidentService`.
  - Preparado estructuralmente para incorporar futuros adaptadores primarios como **MCP** sin duplicar lógica de negocio ni alterar el núcleo.
- **`src/adapters/outbound/` (Adaptadores Secundarios)**:
  - Implementaciones intercambiables de los puertos definidos en `src/application/ports.py`.
  - La selección del adaptador de persistencia ocurre únicamente en el *composition root* mediante la variable de entorno **`DATABASE_URL`**.

### III. Gobernanza Técnica y Stack Aprobado

- **Entorno y lenguaje**: **Python `>=3.10`** gestionado exclusivamente con **`uv`** (`pyproject.toml` y `uv.lock`; toda ejecución mediante `uv run`).
- **Stack tecnológico aprobado**:
  - **API REST (`inbound`)**: **FastAPI** + **Pydantic v2** para contratos y validación en la frontera HTTP.
  - **CLI (`inbound`)**: **Typer**.
  - **Persistencia (`outbound`)**: **`sqlite3` de la librería estándar** con SQL explícito y parametrizado, **sin ORMs pesados** según **`ADR-001`**, evitando escaneos completos en memoria y consultas N+1.
- **Evolución de motor de base de datos**: Cualquier sustitución de `sqlite3` por otro motor relacional o decisión estructural irreversible requiere **emitir y aprobar previamente un ADR específico** en `docs/adr/` siguiendo la plantilla MADR (`docs/adr/000-template.md`).

### IV. Verificación Estática y Pruebas BDD Obligatorias — NON-NEGOTIABLE

- **Verificación estática de fronteras hexagonales**: Todo cambio en `src/` debe pasar la verificación estática de calidad y fronteras de importación con **Ruff** mediante:
  ```bash
  uv run ruff check src/
  ```
- **Especificación y pruebas BDD**:
  - Todo comportamiento nuevo o modificado debe especificarse con escenarios **BDD (`Given / When / Then`)**.
  - La suite automatizada debe ejecutarse y aprobarse obligatoriamente con:
    ```bash
    uv run pytest -v
    ```
  - Las pruebas deben cubrir el determinismo del dominio, los casos de uso mediante puertos en memoria y los adaptadores REST, CLI y de persistencia.

## Development Workflow & Quality Gates

- **Ciclo Plan → Build**: Todo trabajo sigue estrictamente dos fases: planificación/análisis previo con aprobación explícita antes de modificar código o dependencias, seguido de implementación y verificación automatizada.
- **Compuertas obligatorias antes de dar por completada una tarea**:
  1. Cumplimiento de fronteras hexagonales (`src/domain/` sin imports externos; `adapters -> application -> domain`).
  2. Verificación estática limpia con `uv run ruff check src/`.
  3. Suite BDD y unitaria en verde con `uv run pytest -v`.

## Governance

- Esta Constitución prevalece sobre cualquier convención informal o guía operativa. `AGENTS.md` describe el estado operativo vigente del repositorio, mientras que esta Constitución define las reglas normativas invariantes.
- **Enmiendas**: Toda modificación a principios invariantes o al stack aprobado requiere documentación explícita (y ADR en `docs/adr/` cuando sea una decisión arquitectónica), aprobación del responsable del proyecto y actualización del número de versión siguiendo versionado semántico (`MAJOR.MINOR.PATCH`).
- **Sincronización**: `.specify/memory/constitution.md` y `docs/constitution.md` deben mantenerse alineados ante cualquier enmienda.

**Version**: 1.0.0 | **Ratified**: 2026-11-23 | **Last Amended**: 2026-11-23

