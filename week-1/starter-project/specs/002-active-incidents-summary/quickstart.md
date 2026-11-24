# Quickstart Validation Guide: Hito 002 — Resumen de Incidentes Activos

**Branch**: `002-active-incidents-summary` | **Spec**: [spec.md](spec.md)

## Prerrequisitos

Ejecutar todos los comandos desde `week-1/starter-project/` con `uv`:

```bash
uv sync
```

## 1. Validación Estática de Fronteras Hexagonales (Ruff)

Verificar que las reglas `TID251` y `TID252` se cumplen en todas las capas de `src/`:

```bash
uv run ruff check src/
```

**Resultado esperado**: Código de salida `0` (`All checks passed!`).

## 2. Suite de Pruebas BDD y Contrato de Puerto

Ejecutar la suite completa (regresión Hito 001 + nuevos escenarios Hito 002 + cumplimiento de `IncidentRepositoryPort`):

```bash
uv run pytest -v
```

**Resultado esperado**: Todas las pruebas en verde, incluyendo los 4 escenarios BDD de `tests/test_spec_002_summary.py` y la verificación `isinstance(repo, IncidentRepositoryPort)`.

## 3. Validación Manual por CLI

Consultar el resumen contra una base de datos SQLite local (o en memoria por defecto):

```bash
uv run python -m src.adapters.inbound.cli summary
uv run python -m src.adapters.inbound.cli summary --component payments-gateway --reference-time 2026-11-20T12:00:00
```

**Resultado esperado**: Código de salida `0` y JSON válido en `stdout` con `total_active`, `breached_count` e `incidents` (ver [contracts/cli.md](contracts/cli.md)).

## 4. Validación Manual por API HTTP

Iniciar el servidor FastAPI y consultar el endpoint:

```bash
uv run uvicorn src.adapters.inbound.api.app:app --reload
```

En otra terminal:

```bash
curl "http://127.0.0.1:8000/api/v1/incidents/summary"
curl "http://127.0.0.1:8000/api/v1/incidents/summary?component=payments-gateway&reference_time=2026-11-20T12:00:00"
```

**Resultado esperado**: Respuesta `200 OK` con JSON conforme a [contracts/http-api.md](contracts/http-api.md).
