# AGENTS.md — IncidentOps (Estado Actual — Hito 001)

Este archivo define el contexto operativo actual del repositorio `incidentops-starter` para agentes de IA y desarrolladores. Describe **únicamente** lo que existe hoy en el proyecto.

## 1. Regla de Flujo de Trabajo: Modo Plan → Modo Build

Todo trabajo sobre este repositorio debe alternar estrictamente dos fases:

1. **Modo Plan (Solo lectura y análisis)**:
   - Inspeccionar código, ADRs, especificaciones, datos y dependencias sin modificar archivos ni ejecutar comandos destructivos.
   - Diagnosticar problemas, proponer cambios concretos y presentar un plan explícito.
   - **No escribir código ni editar archivos** hasta recibir aprobación explícita del usuario.
2. **Modo Build (Escritura y verificación)**:
   - Ejecutar únicamente los cambios aprobados en el plan.
   - Verificar cada cambio ejecutando `uv run pytest` y los módulos correspondientes con `uv run python -m`.
   - No agregar librerías externas no aprobadas ni anticipar arquitectura futura.

---

## 2. Entorno y Dependencias Actuales

Definidos en `pyproject.toml`:
- **Proyecto**: `incidentops-starter` (`0.1.0`, `[tool.uv] package = false`).
- **Python**: `>=3.10`.
- **Gestor de entorno**: `uv` (`uv sync` para inicializar o sincronizar el entorno virtual).
- **Dependencias de ejecución**:
  - `fastapi>=0.115.0`, `uvicorn>=0.32.0`, `pydantic>=2.9.0` (adaptador primario HTTP REST).
  - `typer>=0.12.0` (adaptador primario CLI).
  - `tiktoken>=0.8.0` (medición exacta de tokens BPE en `src/context_audit.py`).
- **Dependencias de desarrollo (`[dependency-groups] dev`)**:
  - `pytest>=8.3.0`, `httpx>=0.27.0` (pruebas automatizadas y `TestClient` de FastAPI).
- **Configuración de pruebas (`[tool.pytest.ini_options]`)**: `pythonpath = ["."]`, `testpaths = ["tests"]`.
- **Restricción de fronteras**: `src/domain/` y `src/application/` utilizan exclusivamente la librería estándar de Python (cero dependencias de FastAPI, Pydantic, Typer o SQL).

---

## 3. Estructura Hexagonal y Comandos de Ejecución (`src/` y `tests/`)

Todos los comandos deben ejecutarse desde la raíz del proyecto (`week-1/starter-project/`) con `uv run`:

| Capa / Módulo | Propósito actual | Comando de ejecución |
| :--- | :--- | :--- |
| `src/domain/models.py` | Entidades y tipos puros de dominio (`SeverityLevel`, `IncidentStatus`, `TeamName`, `SLARule`, `Incident`, `SLAEvaluation`, `TriageResult`). | *(Importado por dominio, aplicación y adaptadores)* |
| `src/domain/sla_calculator.py` | Cálculo determinista de SLA (`evaluate_sla_status`): 24/7 para `P0`/`P1` y horario hábil Lun–Vie 08:00–18:00 en $O(D)$ para `P2`/`P3`, con validaciones de 6 casos borde. | `uv run python -m src.domain.sla_calculator` |
| `src/domain/triage_rules.py` | Motor determinista de clasificación y enrutamiento (`classify_incident_report`) sobre `data/sample_incidents.json`. | `uv run python -m src.domain.triage_rules` |
| `src/application/services.py` | Capa de aplicación compartida: `IncidentService.triage_incident(incident_id, raw_text)` y `ValidationError` (stateless, agnóstico al transporte). | *(Invocado por los adaptadores HTTP y CLI)* |
| `src/adapters/inbound/api/` | Adaptador primario HTTP (`schemas.py` con Pydantic v2 y `app.py` con `create_app()` y `POST /api/v1/incidents/triage`). | `uv run uvicorn src.adapters.inbound.api.app:app --reload` |
| `src/adapters/inbound/cli.py` | Adaptador primario CLI con Typer (`triage --incident-id <id> --raw-text <texto>`), salida JSON en `stdout` y código `1` ante error de validación. | `uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "HTTP 502 Bad Gateway en pasarela de pagos"` |
| `src/incident_repository.py` | Persistencia heredada en SQLite (`incidents` y `sla_policies`) y benchmark sobre registros sintéticos (pendiente de migración a `src/adapters/outbound/`). | `uv run python -m src.incident_repository` |
| `src/context_audit.py` | Auditoría de consumo de tokens con `tiktoken` (Fuerza Bruta vs. `grep` vs. AST/LSP y comparación de formatos). | `uv run python -m src.context_audit --symbol evaluate_sla_status` |
| `tests/conftest.py` y `tests/test_spec_001_triage.py` | Suite de pruebas de aceptación BDD para Spec 001 usando `fastapi.testclient.TestClient` y `typer.testing.CliRunner`. | `uv run pytest` |

---

## 4. Registros de Decisiones Arquitectónicas (`docs/adr/`) y Especificaciones (`specs/`)

Antes de modificar lógica de negocio o arquitectura, consultar:

- **`docs/constitution.md`**: Principios invariantes de dominio determinista único, arquitectura hexagonal y gobernanza técnica.
- **`docs/adr/000-template.md`**: Plantilla oficial MADR para documentar nuevas decisiones arquitectónicas.
- **`docs/adr/002-calculo-sla-horario-habil.md`** (*Estado: Aceptado*): Cálculo determinista de SLA en horario hábil (Lun–Vie 08:00–18:00) en $O(D)$ y regla de `requires_escalation`. Afecta a `src/domain/sla_calculator.py`.
- **`docs/adr/003-arquitectura-hexagonal.md`**: Adopción de Arquitectura Hexagonal (Puertos y Adaptadores) con fronteras estrictas `adapters -> application -> domain`.
- **`specs/001-triage-endpoint-manual.md`**: Especificación BDD del Hito 001 (triaje stateless vía HTTP y CLI).
