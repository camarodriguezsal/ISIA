# Feature Specification: Resumen de Incidentes Activos

**Feature Branch**: `002-active-incidents-summary`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "Necesitamos consultar el resumen de incidentes actualmente activos (`OPEN` e `IN_PROGRESS`) tanto por API HTTP como por CLI, indicando el total activo, cuántos incumplieron su SLA y el detalle de cada incidente (título, componente, severidad, estado, minutos transcurridos y si requiere escalamiento), permitiendo filtrar opcionalmente por componente."

## Clarifications

### Session 2026-11-23

- Q: Definiciones confirmadas para interfaces, estado vacío, tiempo de referencia y escenarios BDD del Hito 002 → A:
  - Interfaces: `GET /api/v1/incidents/summary` con query parameter opcional `component` (y `reference_time` opcional), y subcomando CLI `summary [--component ...] [--reference-time ...]`.
  - Estado vacío: si no existen incidentes activos (o no hay coincidencias para el componente), retorna `200 OK` / JSON válido con `total_active=0`, `breached_count=0` e `incidents=[]`.
  - Tiempo de referencia: parámetro opcional `reference_time` para evaluaciones deterministas (por defecto, el instante actual).
  - Escenarios BDD: incluir 4 escenarios BDD (`Given / When / Then`) en lenguaje de negocio: resumen global excluyendo `RESOLVED`, resumen filtrado por componente, caso vacío y consulta equivalente por CLI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar el resumen global de incidentes activos vía HTTP (Priority: P1)

Como operador o consumidor del tablero web de IncidentOps, necesito consultar el resumen consolidado de todos los incidentes actualmente activos (`OPEN` e `IN_PROGRESS`) a través de `GET /api/v1/incidents/summary`, con soporte opcional de `reference_time`, para conocer cuántos incidentes siguen activos, cuántos incumplieron su SLA y el detalle operativo de cada uno.

**Why this priority**: Es la capacidad principal del hito; proporciona visibilidad inmediata y determinista sobre la carga operativa vigente y los incumplimientos de SLA.

**Independent Test**: Puede probarse de forma independiente registrando incidentes en estados `OPEN`, `IN_PROGRESS` y `RESOLVED`, consultando `GET /api/v1/incidents/summary` con un `reference_time` fijo y verificando `total_active`, `breached_count` y el listado `incidents`.

**Acceptance Scenarios**:

1. **Escenario 1 — Resumen global excluyendo `RESOLVED`**: **Given** existen incidentes registrados en estados `OPEN`, `IN_PROGRESS` y `RESOLVED`, donde al menos un incidente activo ha superado su presupuesto de SLA en el instante de referencia y otro se mantiene dentro de su SLA, **When** un cliente consulta `GET /api/v1/incidents/summary` sin filtro de componente (opcionalmente indicando `reference_time`), **Then** el sistema responde `200 OK` con un JSON que excluye los incidentes `RESOLVED`, informa `total_active` con la cantidad de incidentes en `OPEN` e `IN_PROGRESS`, informa `breached_count` con la cantidad de incidentes activos que incumplieron su SLA y lista en `incidents` el detalle de cada incidente activo (identificador, título, componente, severidad, estado, minutos transcurridos y si requiere escalamiento).

---

### User Story 2 - Filtrar el resumen por componente y manejar estado vacío (Priority: P2)

Como líder técnico o miembro de un equipo responsable de un componente específico, necesito filtrar el resumen de incidentes activos mediante el parámetro opcional `component` y recibir una respuesta vacía válida cuando no haya coincidencias o no existan incidentes activos.

**Why this priority**: Permite enfocar la supervisión operativa en un componente concreto y garantiza un comportamiento predecible y sin errores cuando no existen incidentes activos.

**Independent Test**: Puede probarse de forma independiente consultando `GET /api/v1/incidents/summary?component=<nombre>` tanto para un componente con incidentes activos como para un escenario sin incidentes activos o sin coincidencias.

**Acceptance Scenarios**:

2. **Escenario 2 — Resumen filtrado por componente**: **Given** existen incidentes activos distribuidos en varios componentes (por ejemplo, `payments-gateway` y `auth-service`), **When** un cliente consulta `GET /api/v1/incidents/summary?component=payments-gateway`, **Then** el sistema responde `200 OK` devolviendo en `incidents` únicamente los incidentes activos pertenecientes a `payments-gateway`, y calculando `total_active` y `breached_count` exclusivamente sobre ese subconjunto.
3. **Escenario 3 — Caso vacío**: **Given** no existen incidentes activos (`OPEN` o `IN_PROGRESS`) en el sistema o no hay coincidencias activas para el componente filtrado, **When** un cliente consulta `GET /api/v1/incidents/summary` (con o sin `component`), **Then** el sistema responde `200 OK` con un JSON válido que contiene `total_active=0`, `breached_count=0` e `incidents=[]`.

---

### User Story 3 - Consultar el resumen equivalente desde la CLI (Priority: P3)

Como operador de soporte o ingeniero de guardia que trabaja desde la terminal, necesito ejecutar el subcomando `summary [--component ...] [--reference-time ...]` para obtener el mismo resumen estructurado que la interfaz HTTP.

**Why this priority**: Garantiza paridad operativa entre web y terminal para equipos de guardia y permite automatizar auditorías de SLA desde la consola.

**Independent Test**: Puede probarse de forma independiente ejecutando `summary` desde la CLI con y sin `--component` y `--reference-time`, verificando que la salida JSON en salida estándar coincide con la respuesta de `GET /api/v1/incidents/summary`.

**Acceptance Scenarios**:

4. **Escenario 4 — Consulta equivalente por CLI**: **Given** existen incidentes activos en el sistema (con distintos estados, componentes y tiempos de creación), **When** un operador ejecuta el subcomando CLI `summary` (opcionalmente con `--component` y/o `--reference-time`), **Then** el comando finaliza con código de salida `0` e imprime en salida estándar un objeto JSON válido con `total_active`, `breached_count` e `incidents` equivalente al devuelto por `GET /api/v1/incidents/summary` para los mismos parámetros y estado de datos.

---

### Edge Cases

- **Sin incidentes activos**: Si no existen registros o todos los incidentes están en estado `RESOLVED`, el resumen devuelve `200 OK` / JSON válido con `total_active=0`, `breached_count=0` e `incidents=[]`.
- **Componente sin coincidencias**: Filtrar por un componente válido que no tiene incidentes activos devuelve `200 OK` / JSON válido con `total_active=0`, `breached_count=0` e `incidents=[]`.
- **Filtro de componente vacío o en blanco**: Si el usuario envía explícitamente `component` vacío (`""`) o compuesto solo por espacios (`"   "`), el sistema rechaza la solicitud con un error de validación claro tanto en HTTP como en CLI.
- **Formato inválido de `reference_time`**: Si se suministra un `reference_time` que no corresponde a una fecha/hora ISO-8601 válida, el sistema rechaza la solicitud con un error de validación claro tanto en HTTP como en CLI.
- **Incidente en umbral preventivo de escalamiento (75%) sin incumplimiento aún**: Un incidente activo que alcanzó el 75% de su presupuesto de SLA pero aún no superó el 100% reporta `requires_escalation=true`, pero **no** incrementa `breached_count`.
- **Incidentes `P2`/`P3` fuera de horario hábil**: Si un incidente `P2` o `P3` fue creado en fin de semana o fuera del horario hábil (08:00–18:00 Lunes a Viernes), los minutos transcurridos contabilizan únicamente tiempo hábil efectivo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST permitir consultar un resumen consolidado de los incidentes actualmente activos, considerando exclusivamente los incidentes cuyo estado sea `OPEN` o `IN_PROGRESS` (excluyendo `RESOLVED`).
- **FR-002**: El resumen MUST incluir `total_active` (número total de incidentes activos en el resultado) y `breached_count` (cantidad de incidentes activos del resultado que han incumplido su SLA).
- **FR-003**: El resumen MUST incluir `incidents` con el detalle de cada incidente activo: identificador, título, componente, severidad, estado, minutos transcurridos según su política de SLA y el indicador booleano de si requiere escalamiento.
- **FR-004**: El cálculo de minutos transcurridos, incumplimiento de SLA y necesidad de escalamiento MUST aplicar una única fuente de verdad determinista conforme a las políticas vigentes de SLA (24/7 para `P0`/`P1`, horario hábil Lunes a Viernes 08:00–18:00 para `P2`/`P3`, y escalamiento al alcanzar el 75% del presupuesto de SLA o al superarlo).
- **FR-005**: El sistema MUST soportar un parámetro opcional `reference_time` (tanto en HTTP como en CLI) para evaluar el SLA de forma determinista respecto a un instante dado; cuando se omite, MUST usar el instante actual del sistema.
- **FR-006**: El sistema MUST permitir filtrar opcionalmente el resumen por el atributo `component`; cuando se aplica el filtro, `incidents`, `total_active` y `breached_count` MUST calcularse exclusivamente sobre los incidentes activos de ese componente.
- **FR-007**: El sistema MUST exponer esta capacidad con paridad funcional y de datos mediante `GET /api/v1/incidents/summary` (con query parameters opcionales `component` y `reference_time`) y el subcomando CLI `summary [--component ...] [--reference-time ...]`.
- **FR-008**: Cuando no existan incidentes activos o no haya coincidencias para el componente solicitado, el sistema MUST responder con `200 OK` / código de salida `0` y JSON válido con `total_active=0`, `breached_count=0` e `incidents=[]`.
- **FR-009**: El sistema MUST rechazar con un error de validación claro cualquier invocación que suministre un filtro `component` vacío/solo espacios o un `reference_time` con formato inválido, tanto en HTTP como en CLI.

### Key Entities *(include if feature involves data)*

- **Resumen de Incidentes Activos**: Vista consolidada resultante de la consulta; contiene `total_active`, `breached_count` y la lista `incidents` con el detalle evaluado de cada incidente activo.
- **Detalle de Incidente Activo**: Representación resumida y evaluada de un incidente en estado `OPEN` o `IN_PROGRESS`; incluye identificador, título, componente afectado, severidad (`P0`–`P3`), estado actual, minutos transcurridos efectivos y bandera de requerimiento de escalamiento.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Los operadores pueden obtener el resumen completo de incidentes activos (`total_active`, `breached_count` e `incidents`) en una sola consulta desde HTTP o CLI, con 100% de consistencia en los valores reportados entre ambas interfaces para el mismo estado de datos y `reference_time`.
- **SC-002**: El 100% de los cálculos de minutos transcurridos, incumplimientos de SLA y necesidad de escalamiento coinciden exactamente con las reglas de negocio deterministas de SLA en todos los escenarios de severidad (`P0`, `P1`, `P2`, `P3`) y horarios (hábil y no hábil).
- **SC-003**: Al filtrar por componente, el 100% de los incidentes retornados pertenecen al componente solicitado y los totales agregados reflejan exactamente el subconjunto filtrado, respondiendo en menos de 1 segundo bajo cargas operativas típicas.
- **SC-004**: Los 4 escenarios de aceptación BDD (resumen global excluyendo `RESOLVED`, resumen filtrado por componente, caso vacío y consulta equivalente por CLI) se verifican exitosamente de forma automatizada.

## Assumptions

- **Estados activos**: Se consideran activos exclusivamente los estados `OPEN` e `IN_PROGRESS`, excluyendo `RESOLVED`.
- **Instante de evaluación del SLA**: Cuando `reference_time` no se proporciona, se utiliza el instante actual del sistema al momento de ejecutar la consulta.
- **Coincidencia del filtro por componente**: El filtro por componente realiza una coincidencia exacta sobre el nombre del componente del incidente.
- **Alcance de lectura**: Esta funcionalidad es de solo lectura; no modifica el estado de los incidentes ni dispara notificaciones externas de escalamiento.
- **Formato de salida en CLI**: Para mantener coherencia con el comportamiento existente en la CLI del proyecto, la salida exitosa se imprime como JSON válido en salida estándar (`stdout`).
