# CLI Contract: Active Incidents Summary

**Command**: `uv run python -m src.adapters.inbound.cli summary`

## Options

| Opción | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `--component` | `TEXT` | No | Filtra el resumen por componente exacto. Valores vacíos o solo espacios producen error de validación en `stderr` y código de salida `1`. |
| `--reference-time` | `TEXT` (ISO-8601) | No | Instante de referencia para evaluación determinista de SLA (ej. `2026-11-20T12:00:00`). Formatos inválidos producen error de validación en `stderr` y código de salida `1`. |

## Environment Variables

- `DATABASE_URL`: URL de conexión para el repositorio (por defecto `sqlite:///:memory:`). Resuelta mediante `src.adapters.outbound.factory.create_repository()`.

## Output (`exit code 0`)

Imprime en `stdout` un objeto JSON válido con la misma estructura exacta que `GET /api/v1/incidents/summary`:

```json
{"total_active": 0, "breached_count": 0, "incidents": []}
```

## Errors (`exit code 1`)

- Imprime mensaje descriptivo en `stderr` (`Error de validación: ...`) y finaliza con código de salida `1`.
