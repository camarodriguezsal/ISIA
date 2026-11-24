# Bitácora de Desarrollo Guiado por Especificaciones (SDD) — IncidentOps (`SDD_LOG.md`)

**Estudiante(s)**: Camilo Andres Rodriguez Salamanca  
**Fecha**: 2026-11-24  
**Entorno de Desarrollo**: Antigravity IDE (`uv` + Python `>=3.10` + Ruff + Pytest + Docker Compose)  
**Modelos Empleados por Fase**:
- **Fase de Arquitectura, Gobernanza y Especificación (Modo Plan — ADRs, Constitución, Specs BDD)**: Modelos de razonamiento extendido en Antigravity IDE (análisis de trade-offs estructurales, diseño de fronteras hexagonales y detección de casos borde en `ADR-003`, `ADR-004` y `specs/002`–`004`).
- **Fase de Implementación, Pruebas y Documentación (Modo Build — Código, Adaptadores, Tests, Bitácora)**: Modelos rápidos/estándar y de razonamiento ligero en Antigravity IDE (ejecución acotada sobre contratos ya cerrados en `spec.md`/`tasks.md`, generación de adaptadores SQLite/PostgreSQL, pruebas BDD y documentación operativa).

---

## 1. Arquitectura, Gobernanza y Planificación (`ROADMAP.md`, ADRs, `constitution.md` y `AGENTS.md`)

### 1.1 Evolución del Proyecto y Gobernanza Viva
IncidentOps partió de un paquete plano en `src/` donde la lógica pura de dominio convivía con acceso directo a `sqlite3` y scripts de demostración (`src/incident_repository.py`). Para escalar hacia múltiples canales de entrada (HTTP REST, CLI y futuro MCP) y un motor relacional dedicado sin degradar el determinismo del núcleo, se estableció una jerarquía clara de artefactos de gobernanza:

1. **Visión de Producto (`docs/ROADMAP.md`)**: Estructuró el trabajo en cuatro hitos incrementales (**H001** Triaje multi-interfaz → **H002** Resumen de incidentes activos → **H003** Ciclo de vida, duplicados y SLA → **H004** Persistencia relacional dedicada y runtime en contenedores).
2. **Constitución del Proyecto (`docs/constitution.md`, v1.1.0)**: Fijó los principios invariantes que ninguna especificación ni implementación puede violar:
   - **Núcleo determinista único (`src/domain/`)**: Cero imports externos; reglas puras de triaje (`classify_incident_report`) y cálculo de SLA (`evaluate_sla_status` en $O(D)$ con horario hábil Lun–Vie 08:00–18:00 para `P2`/`P3` y 24/7 para `P0`/`P1`).
   - **Fronteras hexagonales estrictas (`adapters -> application -> domain`)**: Verificadas estáticamente con Ruff (`select = ["E4", "E7", "E9", "F", "TID"]` y `ban-relative-imports = "parents"`).
   - **Gobernanza de cambios irreversibles**: Ningún cambio de motor de base de datos o topología se implementa sin aprobar previamente su ADR en formato MADR (`docs/adr/000-template.md`).
3. **Contexto Operativo para Agentes (`AGENTS.md`)**: Documentó el flujo obligatorio **Modo Plan → Modo Build** (inspección de solo lectura y aprobación explícita antes de editar archivos), evitando que los agentes de Antigravity IDE introdujeran dependencias no aprobadas o anticiparan arquitectura fuera del hito activo.

### 1.2 Decisiones Arquitectónicas Clave (`ADR-003` y `ADR-004`)
- **`docs/adr/003-arquitectura-hexagonal.md`**: Se descartó una arquitectura N-Tier acoplada a FastAPI/SQLite porque habría obligado a duplicar validaciones en Typer (CLI) o a arrastrar dependencias web hacia herramientas de terminal. En su lugar, se adoptó **Puertos y Adaptadores** usando `typing.Protocol` en `src/application/ports.py` (`IncidentRepositoryPort`) y un servicio compartido agnóstico al transporte (`IncidentService` en `src/application/services.py`).
- **`docs/adr/004-persistencia-postgresql-y-runtime-contenedores.md`**: Al llegar a **H004**, se levantó *parcialmente* la restricción de `ADR-001` ("solo `sqlite3` sin dependencias externas") para incorporar `psycopg[binary]` como driver explícito del adaptador PostgreSQL, **manteniendo la prohibición de ORMs pesados** (SQLAlchemy/SQLModel). Las decisiones técnicas críticas fueron:
  - **Selección en el *composition root* vía `DATABASE_URL`** (`src/adapters/outbound/factory.py`): `sqlite:///:memory:` por defecto para desarrollo y pruebas rápidas; `postgresql://` o `postgres://` para runtime concurrente.
  - **Timestamps ISO-8601 en columnas `TEXT`** en ambos motores: renuncia deliberadamente a aritmética `TIMESTAMPTZ` en SQL para garantizar paridad lexicográfica y cero divergencias de zona horaria frente al motor determinista de SLA en Python (`ADR-002`).
  - **Topología multi-contenedor (`docker-compose.yml`)**: Desacopla `api` (`Dockerfile` con `python:3.12-slim` + `uv`) de `db` (`postgres:16-alpine` con volumen `postgres_data` y `healthcheck` real mediante `pg_isready`), condicionando el arranque de `api` a `service_healthy`.

---

## 2. Desarrollo Guiado por Especificaciones (SDD): Flujo Manual vs. Flujo Estructurado (Spec Kit)

### 2.1 Comparativa Técnica de los Cuatro Hitos
| Hito / Especificación | Enfoque SDD | Artefactos Generados | Alcance Técnico Implementado |
| :--- | :--- | :--- | :--- |
| **001 — `001-triage-endpoint-manual.md`** | SDD Manual (documento único BDD) | 1 archivo Markdown con escenarios `Given/When/Then` | Triaje *stateless* compartido vía `IncidentService.triage_incident`, expuesto en `POST /api/v1/incidents/triage` (FastAPI) y comando `triage` (Typer CLI). |
| **002 — `002-active-incidents-summary/`** | SDD Estructurado (Spec Kit completo) | `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `research.md`, `quickstart.md`, `contracts/`, `checklists/` | Consulta de incidentes activos, conteo de incumplimientos de SLA y filtrado por componente usando `SQLiteIncidentRepository` sobre `IncidentRepositoryPort`. |
| **003 — `003-incident-lifecycle-sla/`** | SDD Estructurado (Spec + Checklists) | `spec.md`, `checklists/` | Registro persistente de incidentes, detección de duplicados abiertos por `duplicate_group_key`, transiciones de estado (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`) y auditoría de SLA en instante de referencia. |
| **004 — `004-postgres-container-runtime/`** | SDD Estructurado (ADR + Spec + Tasks) | `ADR-004`, `spec.md`, `tasks.md`, `checklists/` | `PostgresIncidentRepository` (`psycopg[binary]`), `create_repository` vía `DATABASE_URL`, endpoint `/health` con verificación `SELECT 1`, `Dockerfile` y `docker-compose.yml`. |

### 2.2 Análisis Crítico: Qué Aportó SDD Frente a "Promptear Código Directamente"
1. **Eliminación de deriva entre adaptadores (HTTP vs. CLI)**: Especificar primero el contrato en `Given / When / Then` (por ejemplo, que un `incident_id` vacío o con solo espacios produzca `ValidationError` en aplicación, `422` en FastAPI y código de salida `1` en Typer) impidió que el agente implementara validaciones divergentes en `app.py` y `cli.py`.
2. **Trazabilidad entre requisitos y pruebas (`tests/test_spec_001..004_*.py`)**: Cada archivo de pruebas mapea 1:1 con su especificación. Cuando se introdujo `PostgresIncidentRepository` en H004, la suite existente (`test_spec_001`, `test_spec_002`, `test_spec_003`) actuó como red de regresión inmediata sobre `IncidentService` y `SQLiteIncidentRepository`, mientras `test_spec_004_runtime.py` validó la fábrica `DATABASE_URL` y el contrato de salud.
3. **Trade-off real entre SDD Manual y Spec Kit**:
   - En **H001** (caso de uso *stateless* acotado), un único archivo `001-triage-endpoint-manual.md` fue suficiente y de baja fricción.
   - En **H002–H004** (persistencia, índices SQL, contratos de duplicados y contenedores), descomponer en `spec.md` → `plan.md` → `tasks.md` redujo drásticamente el retrabajo: los errores de diseño (como la paridad de placeholders `?` vs. `%s` o el manejo de `DATABASE_URL` vacía) se detectaron en la revisión del plan y de las tareas antes de tocar `src/`.

---

## 3. Uso de Antigravity IDE, Estrategia de Modelos por Fase y Lecciones Técnicas

### 3.1 Flujo de Trabajo en Antigravity IDE
Trabajar dentro de **Antigravity IDE** permitió integrar directamente la lectura curada del repositorio, la ejecución de verificaciones en terminal (`uv run pytest -v`, `uv run ruff check src/`) y la disciplina **Plan → Build** definida en `AGENTS.md`:
- **Aislamiento de contexto por hito**: En lugar de cargar todo el proyecto en cada turno, se entregaron únicamente los artefactos normativos pertinentes (`docs/constitution.md`, el ADR vigente y la `spec.md` del hito) junto con los módulos exactos de la capa afectada (`src/application/ports.py`, `src/adapters/outbound/factory.py`).
- **Verificación cerrada en el mismo ciclo**: Cada cambio en Modo Build se validó contra Ruff y Pytest antes de dar por completada una tarea de `tasks.md`, evitando acumular deuda de imports cruzados o regresiones silenciosas.

### 3.2 Selección de Modelos por Fase y Trade-offs Observados
| Fase del Ciclo SDD | Tipo de Modelo Empleado en Antigravity IDE | Por Qué Funcionó / Riesgo Mitigado |
| :--- | :--- | :--- |
| **Arquitectura y Gobernanza (`ADR-003`, `ADR-004`, `constitution.md`)** | Modelo de razonamiento extendido (*Thinking*) | Evaluó trade-offs no obvios: por qué mantener SQL explícito sin ORM frente a SQLAlchemy, cómo reemplazar parcialmente `ADR-001` sin romper `ADR-002` (timestamps ISO-8601 en `TEXT`) y cómo aislar `DATABASE_URL` en el *composition root*. |
| **Especificación y Descomposición (`spec.md`, `plan.md`, `tasks.md`)** | Modelo de razonamiento extendido / intermedio | Identificó escenarios de borde antes de codificar: `DATABASE_URL` vacía o con esquema inválido, `DuplicateIncidentIdError` vs. `is_duplicate` por `duplicate_group_key`, y verificación real de salud (`SELECT 1`) en `/health`. |
| **Implementación Acotada (`src/adapters/`, `tests/`, `Dockerfile`, `docker-compose.yml`)** | Modelo rápido / razonamiento ligero | Con contratos y tareas ya cerrados, generó código limpio y determinista con menor latencia y costo, respetando la firma de `IncidentRepositoryPort` y las reglas de `pyproject.toml`. |
| **Revisión de Fronteras y Cierre (`SDD_LOG.md`, checks)** | Modelo rápido / razonamiento ligero | Contrastó directamente los archivos reales del repositorio (`ROADMAP.md`, `ADR-003`, `ADR-004`, `factory.py`, `docker-compose.yml`) para documentar decisiones verificables sin afirmaciones genéricas. |

### 3.3 Lecciones Técnicas Aprendidas
1. **La Arquitectura Hexagonal paga su costo inicial en el Hito 4**: Aunque `ADR-003` añadió módulos y protocolos (`ports.py`, `factory.py`) que parecían excesivos en H001, al llegar a H004 permitió introducir `PostgresIncidentRepository` sin modificar una sola línea de `src/domain/` ni `src/application/`.
2. **Paridad manual SQLite vs. PostgreSQL exige disciplina en pruebas**: Renunciar a un ORM mantiene el SQL transparente y evita N+1, pero traslada la responsabilidad de mantener sincronizados el DDL y los placeholders (`?` en `sqlite3` vs. `%s` en `psycopg`) a los adaptadores y a la suite de pruebas.
3. **Desfase documental en `AGENTS.md`**: Al avanzar rápido hasta H004, `docs/constitution.md` y `docs/ROADMAP.md` se actualizaron, mientras `AGENTS.md` quedó reflejando el estado de H001. Mantener `AGENTS.md` sincronizado al cierre de cada hito es crítico para que los agentes en sesiones futuras no operen con contexto desactualizado.

---

## 4. Evidencia de Verificación Reproducible

Ejecutar todos los comandos desde la raíz del proyecto (`week-1/starter-project/`) y pegar las salidas reales obtenidas en cada bloque.

### 4.1 Verificación Estática y Fronteras Hexagonales (`uv run ruff check src/`)

```bash
uv run ruff check src/
```

```text
All checks passed!
```

### 4.2 Suite Completa de Pruebas BDD (`uv run pytest -v`)

```bash
uv run pytest -v
```

```text
============================================== test session starts ===============================================
platform darwin -- Python 3.12.11, pytest-9.2.0, pluggy-1.7.0 -- /Users/amrodriguez/Documents/Universidad-unal/ISAI/week-1/starter-project/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/amrodriguez/Documents/Universidad-unal/ISAI/week-1/starter-project
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collected 36 items                                                                                               

tests/test_spec_001_triage.py::test_scenario_1_http_502_payments_outage_p0 PASSED                          [  2%]
tests/test_spec_001_triage.py::test_scenario_2_http_individual_account_lockout_with_hoy_no_p0 PASSED       [  5%]
tests/test_spec_001_triage.py::test_scenario_3_http_rejects_empty_or_whitespace_inputs[payload0] PASSED    [  8%]
tests/test_spec_001_triage.py::test_scenario_3_http_rejects_empty_or_whitespace_inputs[payload1] PASSED    [ 11%]
tests/test_spec_001_triage.py::test_scenario_3_http_rejects_empty_or_whitespace_inputs[payload2] PASSED    [ 13%]
tests/test_spec_001_triage.py::test_scenario_4_cli_parity_with_json_stdout PASSED                          [ 16%]
tests/test_spec_001_triage.py::test_scenario_5_cli_rejects_empty_or_whitespace_inputs[args0] PASSED        [ 19%]
tests/test_spec_001_triage.py::test_scenario_5_cli_rejects_empty_or_whitespace_inputs[args1] PASSED        [ 22%]
tests/test_spec_002_summary.py::test_sqlite_repository_fulfills_incident_repository_port PASSED            [ 25%]
tests/test_spec_002_summary.py::test_bdd_scenario_1_global_summary_excludes_resolved_and_evaluates_sla PASSED [ 27%]
tests/test_spec_002_summary.py::test_p2_business_hours_weekend_calculation PASSED                          [ 30%]
tests/test_spec_002_summary.py::test_bdd_scenario_2_summary_filtered_by_component PASSED                   [ 33%]
tests/test_spec_002_summary.py::test_bdd_scenario_3_empty_state_returns_valid_zero_summary PASSED          [ 36%]
tests/test_spec_002_summary.py::test_http_validation_errors_for_blank_component_and_invalid_reference_time PASSED [ 38%]
tests/test_spec_002_summary.py::test_bdd_scenario_4_cli_summary_parity_with_http PASSED                    [ 41%]
tests/test_spec_003_lifecycle_sla.py::test_sqlite_repository_has_dup_key_index_and_fulfills_port PASSED    [ 44%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_scenario_1_create_incident_without_duplicates PASSED        [ 47%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_scenario_2_detect_open_duplicates_ignoring_resolved_and_self PASSED [ 50%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_scenario_3_deterministic_sla_audit_business_hours_p2 PASSED [ 52%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_scenario_4_sla_errors_404_and_422 PASSED                    [ 55%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_scenario_5_cli_create_and_sla_parity PASSED                 [ 58%]
tests/test_spec_003_lifecycle_sla.py::test_edge_cases_validation_and_duplicate_id_conflict PASSED          [ 61%]
tests/test_spec_004_runtime.py::test_bdd_scenario_1_http_health_ok_executes_real_select_1 PASSED           [ 63%]
tests/test_spec_004_runtime.py::test_bdd_scenario_1_cli_health_ok_returns_exit_0_and_json PASSED           [ 66%]
tests/test_spec_004_runtime.py::test_bdd_scenario_2_http_health_unavailable_returns_503 PASSED             [ 69%]
tests/test_spec_004_runtime.py::test_bdd_scenario_2_cli_health_unavailable_returns_exit_1_and_json PASSED  [ 72%]
tests/test_spec_004_runtime.py::test_bdd_scenario_2_postgres_driver_error_returns_false_without_leaking_credentials PASSED [ 75%]
tests/test_spec_004_runtime.py::test_incident_service_check_health_without_repository_raises_runtime_error PASSED [ 77%]
tests/test_spec_004_runtime.py::test_bdd_scenario_3_factory_defaults_to_sqlite_memory_when_unset PASSED    [ 80%]
tests/test_spec_004_runtime.py::test_bdd_scenario_3_factory_selects_sqlite_file PASSED                     [ 83%]
tests/test_spec_004_runtime.py::test_bdd_scenario_3_factory_selects_postgres_for_pg_schemes[postgresql://incidentops:incidentops@db:5432/incidentops] PASSED [ 86%]
tests/test_spec_004_runtime.py::test_bdd_scenario_3_factory_selects_postgres_for_pg_schemes[postgres://incidentops:incidentops@db:5432/incidentops] PASSED [ 88%]
tests/test_spec_004_runtime.py::test_bdd_scenario_3_factory_rejects_empty_or_unsupported_schemes[] PASSED  [ 91%]
tests/test_spec_004_runtime.py::test_bdd_scenario_3_factory_rejects_empty_or_unsupported_schemes[   ] PASSED [ 94%]
tests/test_spec_004_runtime.py::test_bdd_scenario_3_factory_rejects_empty_or_unsupported_schemes[mysql://user:pass@localhost/db] PASSED [ 97%]
tests/test_spec_004_runtime.py::test_bdd_scenario_4_container_artifacts_meet_contract PASSED               [100%]

================================================ warnings summary ================================================
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /Users/amrodriguez/Documents/Universidad-unal/ISAI/week-1/starter-project/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================================= 36 passed, 1 warning in 0.13s ==========================================
```

### 4.3 Verificación del Adaptador Primario CLI (`src.adapters.inbound.cli`)

```bash
uv run python -m src.adapters.inbound.cli triage \
  --incident-id INC-1001 \
  --raw-text "HTTP 502 Bad Gateway en pasarela de pagos"
```

```text
{"incident_id": "INC-1001", "severity": "P0", "component": "payments-gateway", "recommended_team": "Backend-Core", "duplicate_group_key": "payments-gateway:http-502-outage", "rationale": "Indisponibilidad global de servicio crítico de pagos (HTTP 502).", "consistency_ratio": 1.0}
```

### 4.4 Validación de Runtime en Contenedores (`docker compose config` y `docker compose up`)

#### A. Validación de manifiesto (`docker compose config`)
```bash
docker compose config
```

```text
name: starter-project
services:
  api:
    environment:
      DATABASE_URL: postgresql://incidentops:incidentops@db:5432/incidentops
    networks:
      default: null
    build:
      context: /Users/amrodriguez/Documents/Universidad-unal/ISAI/week-1/starter-project
      dockerfile: Dockerfile
    depends_on:
      db:
        condition: service_healthy
        required: true
    healthcheck:
      test:
        - CMD
        - uv
        - run
        - --no-sync
        - python
        - -c
        - import urllib.request; urllib.request.urlopen('http://localhost:8000/health',
          timeout=2)
      timeout: 5s
      interval: 10s
      retries: 5
      start_period: 5s
    ports:
      - mode: ingress
        target: 8000
        published: "8000"
        protocol: tcp
  db:
    environment:
      POSTGRES_DB: incidentops
      POSTGRES_PASSWORD: incidentops
      POSTGRES_USER: incidentops
    image: postgres:16-alpine
    networks:
      default: null
    volumes:
      - type: volume
        source: postgres_data
        target: /var/lib/postgresql/data
        volume: {}
    healthcheck:
      test:
        - CMD-SHELL
        - pg_isready -U incidentops -d incidentops
      timeout: 3s
      interval: 5s
      retries: 10
networks:
  default:
    name: starter-project_default
volumes:
  postgres_data:
    name: starter-project_postgres_data
```

#### B. Levantamiento del stack (`docker compose up`) y verificación de salud (`/health`)
```bash
docker compose up -d --build
docker compose ps
curl -s http://localhost:8000/health
```

```text
 ✔ Image postgres:16-alpine             Pulled                                                               24.7s
 ✔ Image starter-project-api            Built                                                                27.9s
 ✔ Network starter-project_default      Created                                                               0.0s
 ✔ Volume starter-project_postgres_data Created                                                               0.0s
 ✔ Container starter-project-db-1       Healthy                                                               5.6s
 ✔ Container starter-project-api-1      Started                                                               5.7s
NAME                    IMAGE                 COMMAND                  SERVICE   CREATED         STATUS                                     PORTS
starter-project-api-1   starter-project-api   "uv run --no-sync uv…"   api       5 seconds ago   Up Less than a second (health: starting)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
starter-project-db-1    postgres:16-alpine    "docker-entrypoint.s…"   db        5 seconds ago   Up 5 seconds (healthy)                     5432/tcp

{
"status": "ok",
"database": "connected"
}
```
