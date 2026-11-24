# Feature Specification: Ciclo de Vida de Incidentes, Detección de Duplicados y Auditoría de SLA

**Feature Branch**: `003-incident-lifecycle-sla`

**Created**: 2026-11-24

**Status**: Clarified

**Input**: User description: "Necesitamos guardar los incidentes cuando llegan, avisar si ya había otro equivalente abierto, y consultar cómo va su SLA tanto por API HTTP como desde la herramienta CLI. Debe permitir crear incidentes (con título, texto crudo, y campos opcionales como ID autogenerado INC-<HEX8>, fecha de creación y estado por defecto OPEN), detectar duplicados abiertos por clave de grupo excluyendo incidentes RESOLVED y al propio incidente, y consultar el estado de SLA de un incidente en un instante de referencia opcional."

## Clarifications

### Session 2026-11-24

- Q: Definiciones confirmadas para `003-incident-lifecycle-sla` (creación, duplicados, auditoría de SLA y escenarios BDD) → A:
  - **Creación (`POST /api/v1/incidents` y CLI `create`)**:
    - Campos obligatorios: `title` y `raw_text` (rechazando vacíos o solo espacios con `422 Unprocessable Entity` en API / código de salida `1` en CLI).
    - Campos opcionales: `incident_id` (autogenerado `INC-<HEX8>` si se omite), `created_at` (instante actual si se omite) y `status` (default `"OPEN"`).
    - Respuesta `201 Created` (API) o JSON en `stdout` (CLI) incluyendo clasificación completa, `is_duplicate` (`bool`) y `duplicate_of` (`list[str]`).
    - Criterio de duplicado abierto: coincidencia por `duplicate_group_key` únicamente en incidentes abiertos (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`), excluyendo `RESOLVED` y el propio identificador recién creado.
  - **Auditoría de SLA (`GET /api/v1/incidents/{incident_id}/sla` y CLI `sla`)**:
    - Parámetro opcional `reference_time` (ISO-8601) para evaluaciones deterministas.
    - Retorna `404 Not Found` si no existe el incidente, y `422 Unprocessable Entity` si `reference_time < created_at` (código de salida `1` en CLI).
  - **Escenarios BDD mínimos**: 5 escenarios en lenguaje de negocio (`Given / When / Then`): registro inicial `201` sin duplicados, detección de duplicado abierto `201` ignorando `RESOLVED`, auditoría determinista de SLA en horario hábil (`P2` viernes `2026-11-06T17:00:00` → lunes `2026-11-09T09:00:00`), errores de SLA (`404` inexistente y `422` tiempo anterior a creación), y operación equivalente vía CLI `create` y `sla`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registrar y persistir incidentes con triaje automático vía HTTP (Priority: P1)

Como operador o consumidor de la API de IncidentOps, necesito registrar nuevos incidentes mediante `POST /api/v1/incidents` enviando `title` y `raw_text` (y opcionalmente `incident_id`, `created_at` y `status`), para que el sistema los clasifique con el motor determinista de triaje, asigne los valores por defecto cuando se omitan (`INC-<HEX8>`, instante actual y `"OPEN"`), los persista y reporte si existen duplicados abiertos.

**Why this priority**: Es la capacidad base del ciclo de vida de incidentes; sin persistencia al ingreso no es posible detectar duplicados históricos ni auditar el SLA posteriormente.

**Independent Test**: Puede probarse de forma independiente enviando `POST /api/v1/incidents` con `title` y `raw_text`, verificando `201 Created`, el formato `INC-<HEX8>`, `status="OPEN"`, la clasificación determinista (`severity`, `component`, `recommended_team`, `duplicate_group_key`, `rationale`) y `is_duplicate=false` / `duplicate_of=[]`.

**Acceptance Scenarios**:

1. **Escenario 1 — Registro inicial `201` sin duplicados previos**: **Given** el repositorio está operativo y no existen incidentes previos con la misma `duplicate_group_key`, **When** un cliente envía `POST /api/v1/incidents` con `title` y `raw_text` válidos (omitiendo `incident_id`, `created_at` y `status`), **Then** el sistema persiste el incidente y responde `201 Created` con un JSON que contiene un `incident_id` autogenerado con formato `INC-<HEX8>`, `created_at` asignado al instante actual, `status="OPEN"`, la clasificación determinista completa (`severity`, `component`, `recommended_team`, `duplicate_group_key`, `rationale`), `is_duplicate=false` y `duplicate_of=[]`.

---

### User Story 2 - Detectar y avisar duplicados abiertos por `duplicate_group_key` (Priority: P1)

Como operador de soporte, necesito que al crear un incidente el sistema detecte si ya existen otros incidentes equivalentes abiertos con la misma `duplicate_group_key` (`OPEN`, `IN_PROGRESS` o `ESCALATION_REQUIRED`), excluyendo incidentes `RESOLVED` y al propio incidente recién creado, para evitar trabajo duplicado y coordinar la atención.

**Why this priority**: Reduce la fatiga de alertas y el retrabajo operativo ante reportes simultáneos o recurrentes del mismo fallo.

**Independent Test**: Puede probarse registrando un incidente abierto y un incidente `RESOLVED` con la misma `duplicate_group_key`, enviando luego un nuevo incidente equivalente y verificando `is_duplicate=true` y que `duplicate_of` contiene únicamente el ID del incidente abierto previo.

**Acceptance Scenarios**:

2. **Escenario 2 — Detección de duplicado abierto `201` ignorando `RESOLVED`**: **Given** existe un incidente previo `INC-A0000001` en estado abierto (`OPEN`, `IN_PROGRESS` o `ESCALATION_REQUIRED`) y otro incidente previo `INC-R0000001` en estado `RESOLVED`, ambos con la misma `duplicate_group_key`, **When** un cliente registra un nuevo incidente equivalente mediante `POST /api/v1/incidents`, **Then** el sistema persiste el nuevo incidente y responde `201 Created` con `is_duplicate=true` y `duplicate_of=["INC-A0000001"]`, excluyendo tanto a `INC-R0000001` (por estar `RESOLVED`) como al propio identificador recién creado.

---

### User Story 3 - Auditar el estado de SLA de un incidente persistido vía HTTP (Priority: P2)

Como operador o líder técnico, necesito consultar el estado de SLA de un incidente mediante `GET /api/v1/incidents/{incident_id}/sla` con un parámetro opcional `reference_time` (ISO-8601), para evaluar de forma determinista el tiempo transcurrido, el tiempo restante, el incumplimiento de SLA y la necesidad de escalamiento, recibiendo errores claros cuando el incidente no exista o el tiempo de referencia sea inválido.

**Why this priority**: Permite auditar el cumplimiento de SLA de incidentes reales aplicando la política determinista vigente (24/7 para `P0`/`P1` y horario hábil para `P2`/`P3`).

**Independent Test**: Puede probarse registrando un incidente `P2` con `created_at="2026-11-06T17:00:00"`, consultando `GET /api/v1/incidents/{incident_id}/sla?reference_time=2026-11-09T09:00:00`, y probando también un ID inexistente (`404`) y un `reference_time` anterior a `created_at` (`422`).

**Acceptance Scenarios**:

3. **Escenario 3 — Auditoría determinista de SLA en horario hábil (`P2`)**: **Given** existe un incidente `P2` persistido con `created_at="2026-11-06T17:00:00"` (viernes 17:00) y estado `OPEN`, **When** un cliente consulta `GET /api/v1/incidents/{incident_id}/sla?reference_time=2026-11-09T09:00:00` (lunes 09:00), **Then** el sistema responde `200 OK` con `elapsed_minutes=120`, `allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false` y `requires_escalation=false`.
4. **Escenario 4 — Errores de consulta de SLA (`404` inexistente y `422` tiempo anterior a creación)**: **Given** existe un incidente `INC-1001` creado el `2026-11-06T17:00:00` y no existe ningún incidente con ID `INC-99999999`, **When** un cliente consulta `GET /api/v1/incidents/INC-99999999/sla`, **Then** el sistema responde `404 Not Found`; y **When** consulta `GET /api/v1/incidents/INC-1001/sla?reference_time=2026-11-06T16:00:00`, **Then** el sistema responde `422 Unprocessable Entity` con un mensaje de error claro.

---

### User Story 4 - Paridad operativa desde la herramienta CLI (Priority: P3)

Como ingeniero de guardia que trabaja desde la terminal, necesito registrar incidentes con el subcomando `create` y consultar su SLA con el subcomando `sla`, obteniendo una salida JSON estructurada equivalente a la API HTTP y código de salida `1` ante errores.

**Why this priority**: Asegura paridad completa entre los adaptadores primarios HTTP y CLI reutilizando la misma capa de aplicación (`IncidentService`).

**Independent Test**: Puede probarse ejecutando `create` y `sla` vía `CliRunner` (o `uv run python -m src.adapters.inbound.cli`), verificando código de salida `0` y JSON equivalente en `stdout`, así como código `1` y mensaje en `stderr` ante errores de validación o incidente inexistente.

**Acceptance Scenarios**:

5. **Escenario 5 — Operación equivalente mediante CLI `create` y `sla`**: **Given** el repositorio está configurado, **When** un operador ejecuta `create --title "..." --raw-text "..."` (opcionalmente con `--incident-id`, `--created-at` y `--status`), **Then** el comando finaliza con código de salida `0` e imprime en `stdout` un JSON válido equivalente al de `POST /api/v1/incidents` (incluyendo clasificación completa, `is_duplicate` y `duplicate_of`); y **When** ejecuta `sla --incident-id <id> [--reference-time <ISO-8601>]`, **Then** finaliza con código `0` e imprime en `stdout` un JSON válido equivalente al de `GET /api/v1/incidents/{incident_id}/sla`, o finaliza con código `1` y mensaje en `stderr` si el incidente no existe o falla alguna validación.

---

### Edge Cases

- **Campos obligatorios vacíos o solo espacios**: Si `title` o `raw_text` (o `incident_id` cuando se envía explícitamente) están vacíos o contienen solo espacios en blanco, el sistema rechaza la solicitud con `422 Unprocessable Entity` en HTTP y código de salida `1` en CLI.
- **Identificador duplicado (`incident_id` ya existente)**: Si se intenta crear un incidente proporcionando explícitamente un `incident_id` que ya existe en el repositorio, el sistema rechaza la solicitud con `409 Conflict` en HTTP y código de salida `1` en CLI, sin sobrescribir el incidente previo.
- **Estado fuera del catálogo**: Si se proporciona un `status` fuera de `IncidentStatus` (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`), el sistema rechaza la solicitud con `422 Unprocessable Entity` en HTTP y código de salida `1` en CLI.
- **Fechas ISO-8601 inválidas**: Si `created_at` o `reference_time` no cumplen un formato ISO-8601 válido, el sistema rechaza la solicitud con `422 Unprocessable Entity` en HTTP y código de salida `1` en CLI.
- **Solo existen duplicados `RESOLVED`**: Si únicamente hay incidentes previos en estado `RESOLVED` con la misma `duplicate_group_key`, el nuevo incidente retorna `is_duplicate=false` y `duplicate_of=[]`.
- **Incidente en estado `ESCALATION_REQUIRED`**: Cuenta como incidente abierto para la detección de duplicados (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST permitir crear y persistir un incidente recibiendo `title` y `raw_text` como campos obligatorios, y `incident_id`, `created_at` y `status` como campos opcionales.
- **FR-002**: El sistema MUST rechazar valores vacíos o compuestos únicamente por espacios en `title`, `raw_text` (y `incident_id` cuando se suministre explícitamente) con `422 Unprocessable Entity` en HTTP y código de salida `1` en CLI.
- **FR-003**: Cuando `incident_id` se omita al crear un incidente, el sistema MUST autogenerar un identificador con formato `INC-<HEX8>` (prefijo `INC-` seguido de 8 caracteres hexadecimales en mayúsculas).
- **FR-004**: Cuando `created_at` se omita, el sistema MUST usar el instante actual; cuando `status` se omita, MUST asignar `"OPEN"`.
- **FR-005**: Al crear un incidente, el sistema MUST clasificar `raw_text` exclusivamente mediante `classify_incident_report` en `src/domain/triage_rules.py` para derivar `severity`, `component`, `recommended_team`, `duplicate_group_key` y `rationale`.
- **FR-006**: El sistema MUST persistir la `duplicate_group_key` junto con el incidente en el repositorio (`IncidentRepositoryPort` / SQLite) para consultar duplicados por clave de grupo sin escaneos completos en memoria.
- **FR-007**: Al crear un incidente, el sistema MUST detectar duplicados abiertos buscando incidentes con la misma `duplicate_group_key` cuyo estado esté en `("OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED")` (excluyendo `RESOLVED` y excluyendo al propio incidente creado), devolviendo `is_duplicate` (`bool`) y `duplicate_of` (`list[str]`). El incidente nuevo MUST persistirse aunque existan duplicados abiertos.
- **FR-008**: Si se proporciona explícitamente un `incident_id` que ya existe en el repositorio, el sistema MUST rechazar la creación sin sobrescribir el registro (`409 Conflict` en HTTP, código de salida `1` en CLI).
- **FR-009**: El sistema MUST permitir consultar el estado de SLA de un incidente persistido por su `incident_id` aceptando `reference_time` opcional (ISO-8601; por defecto el instante actual) y delegando el cálculo exclusivamente a `evaluate_sla_status` en `src/domain/sla_calculator.py`.
- **FR-010**: Al consultar SLA, el sistema MUST retornar `404 Not Found` si `incident_id` no existe y `422 Unprocessable Entity` si `reference_time < created_at` o si `reference_time` es inválido (código de salida `1` y mensaje en `stderr` en la CLI).
- **FR-011**: El sistema MUST exponer paridad completa entre adaptadores primarios:
  - HTTP: `POST /api/v1/incidents` (`201 Created`) y `GET /api/v1/incidents/{incident_id}/sla` (`200 OK`).
  - CLI: `create --title ... --raw-text ... [--incident-id ...] [--created-at ...] [--status ...]` y `sla --incident-id ... [--reference-time ...]`.

### Key Entities *(include if feature involves data)*

- **Incident (`src/domain/models.py`)**: Entidad de dominio persistida (`incident_id`, `title`, `component`, `severity`, `status`, `created_at`, `resolved_at`, `duplicate_group_key`).
- **CreateIncidentResult (`src/application/services.py`)**: Resultado estructurado del caso de uso de creación; incluye los datos persistidos del incidente, la clasificación completa de triaje (`severity`, `component`, `recommended_team`, `duplicate_group_key`, `rationale`) y el aviso de duplicados (`is_duplicate: bool`, `duplicate_of: list[str]`).
- **SLAEvaluation (`src/domain/models.py`)**: Resultado determinista de auditoría de SLA (`incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached`, `requires_escalation`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Los operadores pueden registrar y persistir incidentes desde HTTP (`201 Created`) o CLI (`create`, exit code `0`) con 100% de consistencia en la clasificación determinista, valores por defecto (`INC-<HEX8>`, `"OPEN"`) y campos `is_duplicate` / `duplicate_of`.
- **SC-002**: El 100% de las detecciones de duplicados abiertos coinciden por `duplicate_group_key` exclusivamente sobre estados `OPEN`, `IN_PROGRESS` y `ESCALATION_REQUIRED`, excluyendo `RESOLVED` y el propio `incident_id`.
- **SC-003**: El 100% de las auditorías de SLA coinciden exactamente con `evaluate_sla_status` (incluyendo el caso de horario hábil `P2` viernes `17:00` → lunes `09:00` = `120` min) y manejan correctamente `404` y `422`.
- **SC-004**: Los 5 escenarios BDD confirmados y los casos borde se verifican automáticamente con `uv run pytest -v` y cumplen las fronteras hexagonales con `uv run ruff check src/`.

## Assumptions

- **Generación de `INC-<HEX8>`**: Se genera con 8 caracteres hexadecimales en mayúsculas (`f"INC-{uuid.uuid4().hex[:8].upper()}"`). Cuando el usuario pasa un `incident_id` explícito, se acepta cualquier cadena no vacía (compatible con IDs como `INC-1001` usados en Specs 001/002).
- **Datetimes ISO-8601**: Consistente con `src/domain/sla_calculator.py` y Spec 002, los timestamps operan en formato ISO-8601 naive (sin desplazamiento de zona horaria) para evaluaciones deterministas de horario hábil `08:00–18:00`.
- **No bloqueo ante duplicados**: Detectar duplicados abiertos informa `is_duplicate=true` y `duplicate_of=[...]`, pero persiste el nuevo incidente.
- **Formato de salida en CLI**: Salida exitosa como JSON válido en `stdout` con código `0`; errores en `stderr` con código `1`.
