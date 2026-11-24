---
name: bdd-acceptance
description: Write Dan North-style BDD (`Given / When / Then`) scenarios in `spec.md` using ubiquitous business language and map them 1:1 to `test_bdd_*` acceptance tests with `TestClient` and `CliRunner`.
---

# BDD Acceptance Testing — IncidentOps

Usa esta skill al redactar especificaciones en `spec.md` y al implementar pruebas de aceptación en `tests/`.

## 1. Redacción de Escenarios BDD en `spec.md` (Estilo Dan North)

Cada comportamiento observable del sistema debe especificarse con escenarios `Given / When / Then` expresados exclusivamente en **vocabulario ubicuo de negocio**:

- **Usar lenguaje de dominio**: incidente, reporte, severidad (`P0`–`P3`), equipo responsable (`Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`), estado (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`), presupuesto de SLA, escalamiento preventivo, incidente duplicado.
- **No filtrar detalles de implementación**:
  - **Evitar** nombres de clases, funciones o módulos Python (`IncidentService`, `SQLiteIncidentRepository`, `classify_incident_report`).
  - **Evitar** nombres de tablas o columnas SQL (`incidents`, `sla_policies`, `duplicate_group_key` como columna SQL).
  - **Evitar** detalles internos de frameworks (`TestClient`, `CliRunner`, `Pydantic`).

### Plantilla de escenario
```markdown
### Escenario: <Título orientado al comportamiento de negocio>
- **Given** <estado inicial del sistema o precondición en términos de negocio>
- **When** <acción que realiza el operador o cliente vía API o CLI>
- **Then** <resultado observable, estado resultante y contrato esperado>
```

## 2. Mapeo 1:1 a Pruebas `test_bdd_*` en `tests/`

Cada escenario definido en `spec.md` debe corresponderse **1:1** con una función de prueba en `tests/` siguiendo estas reglas:

1. **Nomenclatura explícita**:
   - Nombrar cada función `test_bdd_<nombre_del_escenario>` (p. ej., `test_bdd_triage_p0_payments_outage_via_api`, `test_bdd_triage_p0_payments_outage_via_cli`).
   - Incluir en el docstring de la prueba la referencia al escenario (`Given / When / Then`) que verifica.
2. **Cobertura de adaptadores primarios**:
   - **REST**: usar `fastapi.testclient.TestClient` sobre la aplicación creada con `create_app()`.
   - **CLI**: usar `typer.testing.CliRunner` invocando la aplicación Typer y verificando `exit_code` y salida JSON en `stdout`.
   - Verificar **paridad** entre REST y CLI para los mismos casos de uso.
3. **Almacenamiento aislado por prueba**:
   - Nunca compartir una base de datos persistente entre pruebas ni mutar archivos del repositorio.
   - Usar almacenamiento aislado por test (p. ej., `tmp_path` de `pytest` inyectando `DATABASE_URL=sqlite:///<tmp_path>/test.db` vía `monkeypatch.setenv`, o un repositorio en memoria dedicado).
4. **Ejecución obligatoria**:
   ```bash
   uv run pytest -v
   ```

