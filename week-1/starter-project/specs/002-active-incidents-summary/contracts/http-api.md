# HTTP API Contract: Active Incidents Summary

**Endpoint**: `GET /api/v1/incidents/summary`

## Query Parameters

| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `component` | `string` | No | Filtro exacto por nombre de componente. Si se envía vacío o solo espacios (`""`, `"   "`), retorna `422 Unprocessable Entity`. |
| `reference_time` | `string` (ISO-8601 `datetime`) | No | Instante de referencia determinista para evaluar SLA (ej. `2026-11-20T12:00:00`). Si se omite, usa la hora actual. Si el formato es inválido, retorna `422 Unprocessable Entity`. |

## Response `200 OK`

**Schema**: `ActiveIncidentsSummaryResponse` (Pydantic v2 en `src/adapters/inbound/api/schemas.py`)

```json
{
  "total_active": 2,
  "breached_count": 1,
  "incidents": [
    {
      "incident_id": "INC-001",
      "title": "Caída total en pasarela de pagos",
      "component": "payments-gateway",
      "severity": "P0",
      "status": "OPEN",
      "elapsed_minutes": 90,
      "requires_escalation": true
    },
    {
      "incident_id": "INC-002",
      "title": "Latencia elevada en checkout",
      "component": "payments-gateway",
      "severity": "P1",
      "status": "IN_PROGRESS",
      "elapsed_minutes": 60,
      "requires_escalation": false
    }
  ]
}
```

### Empty State (`200 OK`)

Cuando no existen incidentes activos o no hay coincidencias para el componente:

```json
{
  "total_active": 0,
  "breached_count": 0,
  "incidents": []
}
```

## Error Responses

- `422 Unprocessable Entity`: cuando `component` está vacío/en blanco o `reference_time` no es un timestamp ISO-8601 válido.
