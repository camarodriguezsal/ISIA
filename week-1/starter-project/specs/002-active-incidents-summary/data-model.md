# Data Model: Resumen de Incidentes Activos (Hito 002)

**Branch**: `002-active-incidents-summary` | **Date**: 2026-11-23

## 1. Entidades de Dominio Existentes (`src/domain/models.py`)

Se reutilizan sin romper compatibilidad:
- `Incident`: `incident_id: str`, `title: str`, `component: str`, `severity: SeverityLevel`, `status: IncidentStatus`, `created_at: datetime`, `resolved_at: Optional[datetime] = None`.
- `SLAEvaluation`: `incident_id: str`, `severity: SeverityLevel`, `elapsed_minutes: int`, `allowed_minutes: int`, `remaining_minutes: int`, `is_breached: bool`, `requires_escalation: bool`.

## 2. Modelos de Lectura del Caso de Uso (`src/application/services.py`)

### `ActiveIncidentSummaryItem` (dataclass frozen)

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `incident_id` | `str` | Identificador único del incidente |
| `title` | `str` | Título descriptivo del incidente |
| `component` | `str` | Componente afectado |
| `severity` | `SeverityLevel` | Severidad (`P0`, `P1`, `P2`, `P3`) |
| `status` | `IncidentStatus` | Estado activo (`OPEN` o `IN_PROGRESS`) |
| `elapsed_minutes` | `int` | Minutos efectivos transcurridos según política SLA (`evaluate_sla_status`) |
| `requires_escalation` | `bool` | `True` si alcanzó ≥ 75% del presupuesto SLA o está vencido (`is_breached`) |

### `ActiveIncidentsSummary` (dataclass frozen)

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `total_active` | `int` | Cantidad total de incidentes activos en el resultado (`len(incidents)`) |
| `breached_count` | `int` | Cantidad de incidentes activos del resultado con `sla_eval.is_breached == True` |
| `incidents` | `list[ActiveIncidentSummaryItem]` | Lista de detalles evaluados de incidentes activos |

> **Regla de negocio clave**: Un incidente en umbral preventivo (75% ≤ consumo < 100%) tiene `requires_escalation = True` pero `is_breached = False`, por lo que **no** incrementa `breached_count`.

## 3. Puerto Secundario (`src/application/ports.py`)

```python
@runtime_checkable
class IncidentRepositoryPort(Protocol):
    def save_incident(self, incident: Incident) -> None: ...
    def get_incident(self, incident_id: str) -> Optional[Incident]: ...
    def find_open_duplicates(self, component: str, title: str) -> list[Incident]: ...
    def list_active_incidents(
        self, component_filter: Optional[str] = None
    ) -> list[Incident]: ...
    def check_health(self) -> bool: ...
```

## 4. Esquema de Persistencia SQLite (`src/adapters/outbound/sqlite_repository.py`)

### Tabla `sla_policies`
- `severity TEXT PRIMARY KEY`
- `max_resolution_minutes INTEGER NOT NULL`
- `operates_24x7 INTEGER NOT NULL`

Inicializada desde `SLA_POLICY_TABLE` (`src/domain/sla_calculator.py`).

### Tabla `incidents`
- `incident_id TEXT PRIMARY KEY`
- `title TEXT NOT NULL`
- `component TEXT NOT NULL`
- `severity TEXT NOT NULL`
- `status TEXT NOT NULL`
- `created_at TEXT NOT NULL` (ISO-8601)
- `resolved_at TEXT` (ISO-8601 o `NULL`)

### Índice Compuesto Obligatorio
- `CREATE INDEX IF NOT EXISTS idx_incidents_component_status ON incidents (component, status)`

### Consulta Optimizada (`list_active_incidents`)
- Usa `INNER JOIN sla_policies p ON i.severity = p.severity` para evitar consultas N+1.
- Filtra en SQL `i.status IN ('OPEN', 'IN_PROGRESS')` y, cuando `component_filter` no es `None`, añade `AND i.component = ?`.
- Ordena determinísticamente por `i.created_at ASC, i.incident_id ASC`.

## 5. Reglas de Validación

- `component` / `component_filter`: opcional (`None`). Si se suministra como cadena vacía (`""`) o solo espacios (`"   "`), falla con `ValidationError` (HTTP `422`, CLI exit code `1`).
- `reference_time`: opcional (`None` -> `datetime.now()`). Si se suministra en formato no ISO-8601 válido, falla con error de validación (HTTP `422`, CLI exit code `1`).
