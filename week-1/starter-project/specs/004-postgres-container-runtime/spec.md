# Feature Specification: Persistencia PostgreSQL, Chequeo Real de Salud y Runtime en Contenedores

**Feature Branch**: `004-postgres-container-runtime`

**Created**: 2026-11-24

**Status**: Clarified

**Architecture Reference**: `docs/adr/004-persistencia-postgresql-y-runtime-contenedores.md` (`ADR-004`), `docs/adr/003-arquitectura-hexagonal.md` (`ADR-003`), `docs/constitution.md` (`v1.1.0`)

**Input**: User description: "Especifica la feature `004-postgres-container-runtime` respaldada por `ADR-004` y la Constitución actualizada: necesitamos preparar el servicio para ejecutarse en contenedores junto con una base de datos relacional dedicada (`postgres:16-alpine`) y exponer un chequeo real de salud de conectividad (`GET /health` y comando CLI `health`), manteniendo selección transparente entre SQLite (`sqlite:///:memory:` o `sqlite:///...` por defecto sin contenedores) y PostgreSQL (`postgresql://...`) vía `DATABASE_URL`."

## Clarifications

### Session 2026-11-24

- Q: Definiciones confirmadas para `004-postgres-container-runtime` (gobernanza, CLI `health`, esquemas de `DATABASE_URL`, resiliencia y healthcheck en contenedor) → A:
  - **Sincronización documental**: `ADR-004` pasa a estado `Aceptado` y `docs/constitution.md` se enmienda a `v1.1.0` para reflejar la persistencia dual SQLite/PostgreSQL con `psycopg[binary]` sin ORM y la topología multi-contenedor.
  - **Salida del comando CLI `health` ante fallo**: Cuando `check_health()` retorna `False`, el comando imprime `{"status": "error", "database": "unavailable"}` en `stdout` y finaliza con código de salida `1` (paridad JSON exacta con `GET /health`).
  - **Esquemas de `DATABASE_URL`**: `postgresql://` y `postgres://` seleccionan el adaptador PostgreSQL; `sqlite:///` o ausencia de la variable seleccionan el adaptador SQLite (usando `sqlite:///:memory:` por defecto); cualquier otro esquema o cadena vacía lanza `ValueError`.
  - **Resiliencia de conectividad**: Los errores del driver durante `check_health()` se capturan y se traducen a `False` (`503 Service Unavailable` en HTTP / código `1` en CLI) sin tumbar el proceso `api` si la base de datos cae tras el arranque.
  - **Healthcheck del contenedor `api` en `docker-compose.yml`**: Se ejecuta usando librería estándar de Python (`urllib.request` contra `http://localhost:8000/health`), evitando instalar herramientas adicionales como `curl` en `python:3.12-slim`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verificar salud real de conectividad vía HTTP y CLI (Priority: P1)

Como operador SRE, orquestador de contenedores o ingeniero de guardia, necesito consultar el estado de salud real del servicio mediante `GET /health` y el comando CLI `health` ejecutando una consulta `SELECT 1` sobre la base de datos configurada, para confirmar que tanto el proceso de aplicación como el motor de persistencia están operativos antes de enviar tráfico.

**Why this priority**: Un chequeo real de conectividad (`SELECT 1`) es el contrato operativo mínimo para *readiness/liveness probes* en Docker Compose y despliegues en contenedores; un endpoint estático ocultaría fallos de persistencia.

**Independent Test**: Puede probarse de forma independiente contra un repositorio SQLite operativo (`sqlite:///:memory:`) o PostgreSQL activo consultando `GET /health` vía `TestClient` y ejecutando `health` vía `CliRunner`, verificando `200 OK` / código `0` y el cuerpo exacto `{"status": "ok", "database": "connected"}`.

**Acceptance Scenarios**:

1. **Escenario 1 — `GET /health` operativo (`200 OK`) y comando CLI `health`**: **Given** la aplicación está configurada contra una base de datos operativa (SQLite o PostgreSQL) capaz de responder consultas SQL, **When** un cliente consulta `GET /health` o un operador ejecuta el comando CLI `health`, **Then** el adaptador de persistencia ejecuta una consulta real `SELECT 1` sobre la base configurada y el sistema responde `200 OK` en HTTP (o código de salida `0` en CLI con JSON en `stdout`) con el payload exacto `{"status": "ok", "database": "connected"}`.

---

### User Story 2 - Reportar fallo de conectividad de forma explícita y controlada (Priority: P1)

Como orquestador de contenedores o sistema de monitoreo, necesito que cuando el motor de persistencia configurado no sea alcanzable o falle la consulta de salud (`check_health()` retorna `False`), el servicio responda `503 Service Unavailable` en `GET /health` y código de salida `1` en CLI `health` con un payload estructurado de error, sin exponer credenciales ni provocar la caída no controlada del proceso.

**Why this priority**: Permite detectar degradaciones reales de la base de datos y retirar instancias no saludables sin filtrar detalles sensibles ni generar respuestas `500` no controladas.

**Independent Test**: Puede probarse inyectando un repositorio doble/simulado cuyo `check_health()` retorne `False` (o provocando un error controlado del driver) y verificando que `GET /health` retorna `503` con `{"status": "error", "database": "unavailable"}` y que CLI `health` imprime el mismo JSON en `stdout` con código de salida `1`.

**Acceptance Scenarios**:

2. **Escenario 2 — `GET /health` ante fallo de conectividad (`503 Service Unavailable`)**: **Given** el adaptador de persistencia pierde conectividad o falla al ejecutar `SELECT 1` (de modo que `check_health()` retorna `False`), **When** un cliente consulta `GET /health`, **Then** el sistema responde `503 Service Unavailable` con el payload exacto `{"status": "error", "database": "unavailable"}` sin exponer trazas ni credenciales; y **When** un operador ejecuta el comando CLI `health` bajo la misma condición, **Then** el comando imprime `{"status": "error", "database": "unavailable"}` en `stdout` y finaliza con código de salida `1`.

---

### User Story 3 - Seleccionar transparentemente SQLite o PostgreSQL vía `DATABASE_URL` (Priority: P1)

Como desarrollador o administrador de plataforma, necesito que el *composition root* seleccione automáticamente el adaptador SQLite o el adaptador PostgreSQL según el esquema de `DATABASE_URL`, para ejecutar pruebas locales rápidas sin contenedores (`sqlite:///:memory:` por defecto) y operar con PostgreSQL dedicado (`postgresql://...`) sin modificar el núcleo de dominio ni la capa de aplicación.

**Why this priority**: Materializa el principio de puertos y adaptadores (`ADR-003`) y la decisión de persistencia dual sin ORM (`ADR-004`), garantizando portabilidad real entre desarrollo local y producción en contenedores.

**Independent Test**: Puede probarse invocando `create_repository()` con `DATABASE_URL` ausente, `sqlite:///:memory:`, `sqlite:///...`, `postgresql://...`, `postgres://...` y un esquema inválido (`mysql://...`), verificando el tipo de adaptador seleccionado o el lanzamiento de `ValueError`.

**Acceptance Scenarios**:

3. **Escenario 3 — Selección transparente SQLite / PostgreSQL vía `DATABASE_URL`**: **Given** el *composition root* construye el repositorio leyendo la variable de entorno `DATABASE_URL` (o el argumento explícito), **When** `DATABASE_URL` comienza con `postgresql://` (o su alias `postgres://`), **Then** la fábrica selecciona el adaptador PostgreSQL (`PostgresIncidentRepository` con `psycopg` y SQL explícito parametrizado); **When** `DATABASE_URL` comienza con `sqlite:///` o la variable no está definida, **Then** la fábrica selecciona `SQLiteIncidentRepository` (usando `:memory:` por defecto cuando está ausente); y **When** se suministra un esquema no soportado o una cadena vacía, **Then** la fábrica rechaza la configuración con un `ValueError` claro.

---

### User Story 4 - Ejecutar el servicio en 2 contenedores reproducibles (`api` + `db`) (Priority: P2)

Como ingeniero de plataforma o evaluador del proyecto, necesito levantar IncidentOps en un entorno reproducible de 2 contenedores (`api` + `db`) mediante Docker Compose, con volumen persistente para PostgreSQL, espera ordenada de disponibilidad (`depends_on` con `service_healthy`) y verificaciones reales de salud en ambos servicios.

**Why this priority**: Habilita una ejecución portable, aislada y concurrente del servicio completo con base de datos relacional dedicada, lista para validación operativa de extremo a extremo.

**Independent Test**: Puede probarse verificando la estructura de `Dockerfile`, `.dockerignore` y `docker-compose.yml` y ejecutando `docker compose up -d --build`, comprobando que `db` y `api` alcanzan estado `healthy`, `GET /health` retorna `200 OK` y los incidentes creados sobreviven a un reinicio del contenedor `api`.

**Acceptance Scenarios**:

4. **Escenario 4 — Orquestación reproducible en 2 contenedores (`api` + `db`)**: **Given** el repositorio incluye un `Dockerfile` basado en `python:3.12-slim` que instala dependencias reproducibles con `uv`, un `.dockerignore` limpio y un `docker-compose.yml` que define los servicios `db` y `api`, **When** se despliega la pila con Docker Compose, **Then** el servicio `db` (`postgres:16-alpine`) inicializa con un volumen persistente nombrado y valida su salud mediante `pg_isready`, y el servicio `api` arranca únicamente tras `depends_on` con `condition: service_healthy`, conecta a `db` mediante `DATABASE_URL=postgresql://...`, expone la API en el puerto `8000` y valida su propia salud consultando `GET /health` con la librería estándar de Python (`urllib.request`).

---

### Edge Cases

- **`DATABASE_URL` con esquema no soportado o cadena vacía**: Valores como `""`, `"   "` o `"mysql://user:pass@host/db"` deben fallar explícitamente con `ValueError` indicando los esquemas soportados (`sqlite:///`, `postgresql://`, `postgres://`).
- **Caída de PostgreSQL después del arranque de `api`**: Si `db` se detiene o se reinicia mientras `api` está en ejecución, `GET /health` captura el error del driver, retorna `503 Service Unavailable` con `{"status": "error", "database": "unavailable"}` y el proceso `api` permanece vivo para recuperarse automáticamente cuando `db` vuelva a estar disponible (`200 OK`).
- **Reinicio de contenedores con datos persistidos**: Al reiniciar `api` o `db` conservando el volumen nombrado de PostgreSQL, la inicialización de esquema (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `INSERT ... ON CONFLICT`) debe ser completamente idempotente y preservar los incidentes existentes.
- **Paridad temporal ISO-8601 entre SQLite y PostgreSQL**: Un incidente `P2` creado el viernes `2026-11-06T17:00:00` y auditado el lunes `2026-11-09T09:00:00` debe producir exactamente `elapsed_minutes=120` en ambos motores al persistir fechas en `TEXT` ISO-8601 sin conversiones de zona horaria.
- **Operación local sin contenedores**: Ejecutar `uv run pytest -v` o levantar la API/CLI localmente sin definir `DATABASE_URL` debe funcionar íntegramente sobre `sqlite:///:memory:` sin requerir Docker ni un servidor PostgreSQL en ejecución.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La capa de aplicación (`IncidentService` en `src/application/services.py`) MUST exponer un caso de uso de verificación de salud (p. ej., `check_health() -> bool`) que delegue exclusivamente en `IncidentRepositoryPort.check_health()`.
- **FR-002**: El adaptador HTTP (`src/adapters/inbound/api/app.py`) MUST exponer `GET /health` devolviendo `200 OK` con cuerpo JSON `{"status": "ok", "database": "connected"}` cuando `check_health()` retorne `True`.
- **FR-003**: El adaptador HTTP (`GET /health`) MUST devolver `503 Service Unavailable` con cuerpo JSON `{"status": "error", "database": "unavailable"}` cuando `check_health()` retorne `False`.
- **FR-004**: El adaptador CLI (`src/adapters/inbound/cli.py`) MUST exponer el subcomando `health` con paridad funcional: imprime `{"status": "ok", "database": "connected"}` en `stdout` con código de salida `0` si `check_health()` es `True`, e imprime `{"status": "error", "database": "unavailable"}` en `stdout` con código de salida `1` si `check_health()` es `False`.
- **FR-005**: Tanto `SQLiteIncidentRepository` como `PostgresIncidentRepository` MUST ejecutar una consulta SQL real `SELECT 1` dentro de `check_health()` y capturar las excepciones del driver subyacente (`sqlite3.Error` / `psycopg.Error`) retornando `False` en lugar de propagar errores no controlados.
- **FR-006**: El proyecto MUST incorporar un adaptador secundario `PostgresIncidentRepository` en `src/adapters/outbound/` basado en `psycopg[binary]` (sin ORM), implementando completamente el protocolo `IncidentRepositoryPort` (`save_incident`, `get_incident`, `find_open_duplicates`, `list_active_incidents`, `check_health`) con SQL explícito y parametrizado (`%s`).
- **FR-007**: `PostgresIncidentRepository` MUST inicializar de manera idempotente las tablas `sla_policies` e `incidents`, los índices `idx_incidents_component_status` y `idx_incidents_dup_key`, y sembrar `SLA_POLICY_TABLE` (`INSERT ... ON CONFLICT DO UPDATE`), almacenando `created_at` y `resolved_at` como cadenas ISO-8601 en columnas `TEXT`.
- **FR-008**: La fábrica de repositorios (`src/adapters/outbound/factory.py`) MUST seleccionar `PostgresIncidentRepository` cuando `DATABASE_URL` inicie con `postgresql://` o `postgres://`, `SQLiteIncidentRepository` cuando inicie con `sqlite:///` o cuando `DATABASE_URL` no esté definida (usando `sqlite:///:memory:` por defecto), y lanzar `ValueError` ante esquemas no soportados o vacíos.
- **FR-009**: El proyecto MUST incluir un `Dockerfile` basado en `python:3.12-slim` que utilice `uv` y `uv.lock` para instalar dependencias de forma reproducible y ejecute el servidor HTTP (`uvicorn src.adapters.inbound.api.app:app --host 0.0.0.0 --port 8000`).
- **FR-010**: El proyecto MUST incluir un `.dockerignore` limpio que excluya entornos virtuales (`.venv/`), metadatos de control de versiones (`.git/`), cachés (`__pycache__/`, `.pytest_cache/`, `.ruff_cache/`), archivos de bases locales (`*.db`, `*.sqlite*`), documentación temporal y archivos del sistema operativo (`.DS_Store`).
- **FR-011**: El proyecto MUST incluir un `docker-compose.yml` con:
  - Servicio `db` basado en `postgres:16-alpine`, credenciales configurables vía variables de entorno, volumen persistente nombrado montado en `/var/lib/postgresql/data` y `healthcheck` ejecutando `pg_isready`.
  - Servicio `api` construido desde el `Dockerfile` local, `DATABASE_URL` apuntando al host interno `db`, puerto `8000` expuesto, `depends_on` hacia `db` con `condition: service_healthy`, y `healthcheck` validando `http://localhost:8000/health` mediante Python (`urllib.request`).
- **FR-012**: Todos los casos de uso existentes (`H001` triaje, `H002` resumen de incidentes activos, `H003` creación, duplicados y auditoría de SLA) MUST operar con paridad funcional y de datos sobre ambos adaptadores (SQLite y PostgreSQL).

### Requisitos No Funcionales (RNF)

- **RNF-001 (Integridad de Fronteras Hexagonales)**: `src/domain/` y `src/application/` MUST mantener cero dependencias hacia `psycopg`, FastAPI, Pydantic, Typer o detalles SQL (`ADR-003`). La verificación estática `uv run ruff check src/` MUST aprobar sin errores.
- **RNF-002 (Determinismo Temporal Inter-Motor)**: Todas las marcas de tiempo (`created_at`, `resolved_at`) MUST almacenarse como `TEXT` en formato ISO-8601 en SQLite y PostgreSQL (`ADR-004`), evitando conversiones implícitas de zona horaria y asegurando cálculos idénticos de SLA (`ADR-002`).
- **RNF-003 (Rendimiento y Ausencia de ORM)**: Todas las consultas SQL MUST ser explícitas y parametrizadas sin ORMs pesados, respaldadas por índices equivalentes en ambos motores; `GET /health` (`SELECT 1`) MUST responder en menos de `200 ms` en red local/interna de contenedores.
- **RNF-004 (Reproducibilidad y Ligereza de Contenedores)**: La imagen `api` MUST construirse de forma determinista a partir de `python:3.12-slim`, `pyproject.toml` y `uv.lock` (`--frozen`), sin instalar utilidades innecesarias como `curl`, manteniendo un contexto de construcción limpio vía `.dockerignore`.
- **RNF-005 (Seguridad y Confidencialidad Operativa)**: Las credenciales de PostgreSQL MUST inyectarse mediante variables de entorno y NEVER exponerse en respuestas de `GET /health`, salidas de CLI `health` ni mensajes de error hacia clientes externos.
- **RNF-006 (Resiliencia y Arranque Ordenado)**: El servicio `api` MUST esperar a que `db` reporte `service_healthy` antes de iniciar; ante indisponibilidad posterior de la base de datos, `check_health()` MUST degradar de forma controlada (`False` → `503`) sin provocar la terminación del proceso.
- **RNF-007 (Portabilidad de la Suite de Pruebas)**: La ejecución de `uv run pytest -v` en entorno local MUST continuar funcionando sin requerir Docker ni una instancia activa de PostgreSQL, validando los escenarios BDD con SQLite `:memory:` y dobles de prueba para selección y fallos de conectividad.

### Key Entities & Contracts

- **HealthStatus (Contrato HTTP/CLI)**:
  - Operativo: `{"status": "ok", "database": "connected"}` (`200 OK` en HTTP, exit code `0` en CLI).
  - No disponible: `{"status": "error", "database": "unavailable"}` (`503 Service Unavailable` en HTTP, exit code `1` en CLI).
- **IncidentRepositoryPort (`src/application/ports.py`)**: Puerto secundario estructural que declara `check_health(self) -> bool` junto con las operaciones de persistencia de incidentes.
- **Configuración de Runtime (`DATABASE_URL` y Docker Compose)**: Variable de entorno que selecciona el adaptador de salida en el *composition root* (`sqlite:///:memory:` por defecto en local; `postgresql://...@db:5432/...` en contenedores).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `GET /health` y el comando CLI `health` ejecutan `SELECT 1` real y retornan `{"status": "ok", "database": "connected"}` (`200` / exit code `0`) cuando la base está operativa, con 100% de paridad entre ambas interfaces.
- **SC-002**: Ante fallo de conectividad (`check_health() == False`), `GET /health` retorna `503 Service Unavailable` y CLI `health` finaliza con código `1`, ambos con `{"status": "error", "database": "unavailable"}` y cero fuga de credenciales o trazas internas.
- **SC-003**: La fábrica de repositorios selecciona correctamente PostgreSQL (`postgresql://`, `postgres://`) o SQLite (`sqlite:///`, ausente → `:memory:`) y rechaza esquemas inválidos en el 100% de los casos probados.
- **SC-004**: El stack `docker compose up -d --build` levanta los 2 contenedores (`db` y `api`) hasta estado `healthy`, responde `200 OK` en `GET /health` y conserva los incidentes persistidos tras reiniciar el contenedor `api`.
- **SC-005**: Los 4 escenarios BDD, los casos borde y las pruebas previas (`Specs 001–003`) pasan con `uv run pytest -v` y cumplen las fronteras hexagonales con `uv run ruff check src/`.

## Assumptions

- **Dependencia aprobada**: `psycopg[binary]` se incorporará a `pyproject.toml` y `uv.lock` únicamente durante la fase de implementación, respaldada por `ADR-004` (`Aceptado`) y `docs/constitution.md` (`v1.1.0`).
- **Puerto por defecto de la API**: El servicio `api` escucha en el puerto `8000` dentro y fuera del contenedor (configurable mediante variables de entorno si se requiere).
- **Alcance de persistencia**: Esta especificación no introduce un motor de migraciones externo (como Alembic); la evolución del esquema se mantiene idempotente mediante DDL explícito al inicializar el adaptador.
- **Pruebas de integración contra PostgreSQL real**: Las pruebas unitarias/BDD en `pytest` no dependen de Docker para mantenerse portables (`RNF-007`), mientras que la verificación end-to-end contra `postgres:16-alpine` se realiza mediante `docker compose`.
