# ADR-002: Cálculo Determinista de SLA en Horario Hábil y Escalamiento Preventivo

- **Estado**: Aceptado
- **Fecha**: 2026-11-16
- **Autor(es)**: Camilo Andres Rodriguez Salamanca
- **Componentes Afectados**: [`src/sla_calculator.py`]

---

## 1. Contexto y Problema

El motor actual `evaluate_sla_status` en `src/sla_calculator.py` presenta dos defectos críticos de negocio:
1. **Conteo continuo 24/7 indiscriminado**: Calcula `elapsed_minutes` restando marcas de tiempo en calendario continuo para todas las severidades. Sin embargo, según `SLA_POLICY_TABLE`, únicamente `P0` y `P1` (`operates_24x7=True`) operan 24/7. Los incidentes `P2` y `P3` (`operates_24x7=False`) solo deben consumir tiempo de SLA dentro del horario hábil: **Lunes a Viernes de 08:00 a 18:00** (máximo 600 minutos hábiles por día; sábados y domingos suman 0 minutos).
2. **Apagado erróneo de escalamiento tras vencimiento**: La condición `not is_breached` desactiva `requires_escalation` en cuanto un incidente no resuelto supera el 100% de su SLA, silenciando alertas críticas cuando el ticket más requiere intervención.

**Restricciones del sistema**:
- Cero dependencias externas (usar exclusivamente `datetime`, `timedelta` y `time` de la librería estándar de Python).
- Mantener intacta la firma pública `evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation`.
- Complejidad temporal $O(D)$ (donde $D$ es el número de días calendario entre `created_at` y `end_time`), evitando iteraciones minuto a minuto $O(M)$.

---

## 2. Opciones Consideradas

1. **Opción A — Simulación minuto a minuto ($O(M)$)**:
   - *Ventajas*: Implementación trivial mediante un bucle de incrementos de 1 minuto.
   - *Desventajas*: Degradación lineal $O(M)$ cuando un ticket `P3` permanece abierto varias semanas (decenas de miles de iteraciones innecesarias).
2. **Opción B — Librerías externas de calendarios laborales (ej. `business_calendar`, `pandas`)**:
   - *Ventajas*: Manejo nativo de calendarios corporativos.
   - *Desventajas*: Viola la restricción de cero dependencias externas y añade peso innecesario al entorno.
3. **Opción C — Iteración por días calendario con intersección de intervalos ($O(D)$)**:
   - *Ventajas*: Complejidad $O(D)$ (1 iteración por día entre creación y evaluación), aritmética exacta de intersección `[max(inicio_ventana, created_at), min(fin_ventana, end_time)]`, maneja nativamente creaciones fuera de horario o en fin de semana, y usa solo librería estándar.
   - *Desventajas*: Requiere cuidado explícito con el límite superior del día final.

---

## 3. Decisión Arquitectónica

Se selecciona la **Opción C (Iteración por días calendario con intersección de ventanas hábiles $O(D)$)** junto con la corrección de la bandera de escalamiento para incidentes no resueltos que alcancen el umbral del 75% o superen el límite de SLA (`is_breached=True`).

```mermaid
flowchart TD
    A["Inicio: evaluate_sla_status(incident, reference_time)"] --> B{"¿end_time < created_at?"}
    B -- Sí --> C["Lanzar ValueError"]
    B -- No --> D{"¿rule.operates_24x7?"}
    D -- "Sí (P0, P1)" --> E["elapsed = int((end_time - created_at) // 60)"]
    D -- "No (P2, P3)" --> F["Iterar día d desde created_at.date() hasta end_time.date()"]
    F --> G{"¿d.weekday() < 5? (Lun-Vie)"}
    G -- "No (Sáb-Dom)" --> H["Sumar 0 minutos"]
    G -- "Sí" --> I["Intersecar con [created_at, end_time]"]
    I --> J["Sumar max(0, segundos_solapados) al total"]
    H --> K{"¿Más días?"}
    J --> K
    K -- Sí --> F
    K -- No --> L["elapsed = int(total_segundos // 60)"]
    E --> M["remaining = allowed - elapsed<br/>is_breached = elapsed > allowed"]
    L --> M
    M --> N["requires_escalation = (status != 'RESOLVED')<br/>and (is_breached or elapsed >= int(allowed * 0.75))"]
    N --> O["Retornar SLAEvaluation"]
