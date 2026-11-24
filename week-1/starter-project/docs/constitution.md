# Constitución del Proyecto — IncidentOps

Este documento establece los principios invariantes de dominio, arquitectura y gobernanza técnica de **IncidentOps** (sincronizado con `.specify/memory/constitution.md`). A diferencia de `AGENTS.md` (que describe el estado operativo vigente del repositorio y sus comandos actuales), esta Constitución define las reglas normativas que toda especificación, diseño e implementación debe respetar.

---

## 1. Núcleo Determinista Único (`src/domain/`)

Toda la lógica de negocio reside en una única fuente de verdad determinista en `src/domain/` (`models.py`, `triage_rules.py`, `sla_calculator.py`) y **no puede duplicarse ni reinterpretarse** en adaptadores HTTP, comandos CLI, futuros servidores MCP ni consultas SQL:

- **Reglas de triaje y enrutamiento (`triage_rules.py`)**: La clasificación de reportes (`classify_incident_report`) es determinista y evalúa impacto real, seguridad multi-tenant y radio de afectación, ignorando trampas léxicas aisladas (como `"hoy"`).
- **Severidades y cálculo de SLA (`sla_calculator.py`, `SLA_POLICY_TABLE`, `ADR-002`)**:
  - `P0` (`60` min) y `P1` (`240` min): operación continua **24/7**.
  - `P2` (`480` min) y `P3` (`1440` min): **horario hábil Lunes a Viernes de 08:00 a 18:00** (600 min hábiles/día; fines de semana suman 0).
- **Escalamiento preventivo y vencimiento**: `requires_escalation` permanece activo (`True`) siempre que el incidente no esté `RESOLVED` y haya alcanzado al menos el **75%** de su presupuesto de SLA (`escalation_threshold_ratio = 0.75`) o haya superado el límite (`is_breached = True`).
- **Catálogos cerrados (`models.py`)**:
  - **Severidades**: `P0`, `P1`, `P2`, `P3`.
  - **Estados (`IncidentStatus`)**: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`.
  - **Equipos válidos (`TeamName`)**: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`.
- **Clave de duplicados (`duplicate_group_key`)**: Generada exclusivamente por el dominio con formato estricto `<component>:<symptom_category>` para detección consistente de incidentes equivalentes.

---

## 2. Arquitectura Hexagonal Estricta (`ADR-003`)

En cumplimiento de `docs/adr/003-arquitectura-hexagonal.md`, la estructura de `src/` sigue **Puertos y Adaptadores** con inversión estricta de dependencias hacia el núcleo:

- **`src/domain/` (Núcleo Puro)**: Entidades, tipos (`Incident`, `SLARule`, `SLAEvaluation`, `TriageResult`) y reglas puras de triaje y SLA (`models.py`, `triage_rules.py`, `sla_calculator.py`). **Cero imports externos** (exclusivamente librería estándar de Python).
- **`src/application/` (Casos de Uso y Puertos)**: Contratos de puertos secundarios en `ports.py` (`typing.Protocol`) y orquestación compartida en `services.py` (`IncidentService`). No importa detalles de HTTP, terminal ni SQL concreto.
- **`src/adapters/inbound/` (Adaptadores Primarios)**: Interfaces delgadas con **FastAPI** (API REST) y **Typer** (CLI) que traducen entradas/salidas hacia `IncidentService`. El núcleo y la capa de aplicación permanecen agnósticos al transporte para incorporar futuros adaptadores como **MCP** sin duplicar lógica de negocio.
- **`src/adapters/outbound/` (Adaptadores Secundarios)**: Implementaciones intercambiables de los `Protocol` definidos en `src/application/ports.py`, seleccionables vía **`DATABASE_URL`** en el *composition root*.
- **Regla de fronteras**: Las dependencias apuntan exclusivamente hacia el centro (`adapters -> application -> domain`). El ensamblado de adaptadores ocurre únicamente en el *composition root*.

---

## 3. Gobernanza Técnica y Calidad

- **Entorno y lenguaje**: **Python `>=3.10`** gestionado exclusivamente con **`uv`** (`pyproject.toml` y `uv.lock`; ejecución mediante `uv run`).
- **Stack tecnológico aprobado**:
  - **API REST (`inbound`)**: **FastAPI** + **Pydantic v2** para contratos y validación en frontera HTTP.
  - **CLI (`inbound`)**: **Typer**.
  - **Persistencia (`outbound`)**: **`sqlite3` de la librería estándar** con SQL explícito y parametrizado, **sin ORMs pesados** según **`ADR-001`**, evitando anti-patrones de escaneo completo en memoria o consultas N+1.
- **Gobernanza de base de datos y decisiones**: Cualquier cambio de motor de base de datos (p. ej., adopción de un motor relacional dedicado en H004) o decisión estructural irreversible requiere **aprobar previamente su propio ADR** en `docs/adr/` siguiendo la plantilla MADR de `docs/adr/000-template.md`.
- **Verificación estática de fronteras hexagonales**: Validación obligatoria con **Ruff** mediante `uv run ruff check src/`.
- **Especificación y pruebas BDD obligatorias**:
  - Todo comportamiento nuevo o modificado debe especificarse con escenarios **BDD (`Given / When / Then`)**.
  - La verificación automatizada es obligatoria mediante `uv run pytest -v`, cubriendo el determinismo del dominio, los casos de uso mediante puertos en memoria y los adaptadores REST/CLI/SQLite.
- **Flujo operativo**: Todo trabajo sigue el ciclo **Plan → Build**; no se introduce código ni dependencias sin aprobación previa y verificación automatizada tras los cambios.

---

**Version**: 1.0.0 | **Ratified**: 2026-11-23 | **Last Amended**: 2026-11-23
