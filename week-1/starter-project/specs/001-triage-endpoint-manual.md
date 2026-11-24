# Especificación H001 — Triaje Multi-Interfaz (HTTP + CLI)

**Hito**: H001 — Triaje multi-interfaz  
**Estado**: Acordado  
**Referencias**: `docs/constitution.md`, `docs/ROADMAP.md`, `src/triage_rules.py`

---

## 1. Propósito y Alcance

Exponer el motor determinista de clasificación y enrutamiento de incidentes de **IncidentOps** para consumo inmediato desde el frontend (API HTTP) y desde la terminal de soporte (CLI), sin persistencia en base de datos.

### Decisiones de Diseño y Contrato

- **Operación stateless**: No persiste registros en base de datos. Ambos adaptadores primarios invocan un único caso de uso compartido: `IncidentService.triage_incident(incident_id, raw_text)`.
- **Dominio determinista único**: Toda la lógica de clasificación y enrutamiento reside en el núcleo de dominio (`src/domain/`), sin duplicarse en los adaptadores HTTP ni CLI.
- **Adaptador HTTP (FastAPI + Pydantic v2)**:
  - Endpoint: `POST /api/v1/incidents/triage`
  - Entrada JSON: `{"incident_id": "<str>", "raw_text": "<str>"}` (ambos obligatorios).
  - Salida exitosa (`200 OK`): JSON con todos los campos de `TriageResult` (`incident_id`, `severity`, `component`, `recommended_team`, `duplicate_group_key`, `rationale`, `consistency_ratio`).
  - Validación: Si `incident_id` o `raw_text` están vacíos o contienen solo espacios en blanco (`.strip() == ""`), retorna `422 Unprocessable Entity`.
- **Adaptador CLI (Typer)**:
  - Invocación vía `uv run python -m ...` con subcomando `triage --incident-id <id> --raw-text <texto>`.
  - Salida exitosa (código de salida `0`): imprime el mismo `TriageResult` serializado en JSON válido por salida estándar (`stdout`).
  - Validación: Ante entradas vacías o solo espacios, muestra un mensaje de error y finaliza con código de salida `1`.

---

## 2. Escenarios BDD (`Given / When / Then`)

### Escenario 1: Caída crítica HTTP 502 en pasarela de pagos vía HTTP
- **Given** el servicio HTTP de IncidentOps está disponible en modo stateless
- **And** un cliente del frontend necesita clasificar un reporte de caída global de pagos
- **When** el cliente envía una solicitud `POST /api/v1/incidents/triage` con:
  ```json
  {
    "incident_id": "INC-1001",
    "raw_text": "HTTP 502 Bad Gateway en pasarela de pagos"
  }
  ```
- **Then** el servicio responde con estado `200 OK`
- **And** el cuerpo JSON contiene todos los campos de `TriageResult` con:
  - `incident_id`: `"INC-1001"`
  - `severity`: `"P0"`
  - `component`: `"payments-gateway"`
  - `recommended_team`: `"Backend-Core"`
  - `duplicate_group_key`: `"payments-gateway:http-502-outage"`
- **And** no se crea ningún registro persistente en base de datos.

### Escenario 2: Cuenta individual bloqueada mencionando "hoy" (sin falso positivo P0)
- **Given** el servicio HTTP de IncidentOps está disponible en modo stateless
- **And** un usuario reporta un bloqueo de cuenta individual usando la palabra `"hoy"`
- **When** el cliente envía una solicitud `POST /api/v1/incidents/triage` con:
  ```json
  {
    "incident_id": "INC-1002",
    "raw_text": "Mi cuenta está bloqueada y no puedo ingresar hoy"
  }
  ```
- **Then** el servicio responde con estado `200 OK`
- **And** la clasificación asigna `severity`: `"P2"` y `recommended_team`: `"Security-IAM"`
- **And** la severidad **no** se eleva erróneamente a `"P0"` por la presencia de la palabra `"hoy"`.

### Escenario 3: Rechazo de entradas vacías o con solo espacios en blanco vía HTTP
- **Given** el servicio HTTP de IncidentOps está disponible
- **When** un cliente envía `POST /api/v1/incidents/triage` con `raw_text` compuesto solo por espacios (`"   "`) o con `incident_id` vacío (`""`)
- **Then** el servicio rechaza la solicitud con estado `422 Unprocessable Entity`
- **And** no invoca el motor de triaje con datos inválidos.

### Escenario 4: Paridad funcional en CLI con salida JSON
- **Given** el comando CLI de IncidentOps está disponible para el equipo de soporte
- **When** un operador ejecuta el subcomando:
  ```bash
  triage --incident-id INC-1001 --raw-text "HTTP 502 Bad Gateway en pasarela de pagos"
  ```
- **Then** el comando finaliza con código de salida `0`
- **And** imprime en salida estándar (`stdout`) un objeto JSON válido equivalente al resultado del servicio HTTP, con `severity`: `"P0"` y `recommended_team`: `"Backend-Core"`.

### Escenario 5: Rechazo de entradas vacías en CLI
- **Given** el comando CLI de IncidentOps está disponible para el equipo de soporte
- **When** un operador ejecuta `triage` con `--incident-id ""` o `--raw-text "   "`
- **Then** el comando emite un mensaje de error claro
- **And** finaliza con código de salida `1`.
