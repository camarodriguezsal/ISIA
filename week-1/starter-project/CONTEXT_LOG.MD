# Bitácora de Ingeniería de Prompts y Contexto — Semana 1 (`CONTEXT_LOG.md`)

**Estudiante(s)**: Camilo Andres Rodriguez Salamanca  
**Fecha**: 2026-11-16  
**Modelos / Asistentes Utilizados**: Gemini (hydrogen) (Modo Estándar vs. Razonamiento)

---
## 1. De Prompts Pobres a Técnicas Clásicas de *Prompt Engineering* (Reto 1: `src/triage_rules.py`)

### 1.1 Diagnóstico de un Prompt Pobre y Ambiguo
Prompt original enviado por el desarrollador junior:
> *"El archivo `triage_rules.py` funciona mal con algunos tickets del JSON. Agrégale el equipo recomendado y una clave para duplicados, y no pongas P0 cuando no sea urgente."*

Fallos principales de este prompt:
1. **Ambigüedad en los valores permitidos**: No indica cuáles son los 4 equipos válidos (`Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`) ni la estructura `<component>:<symptom_category>` para `duplicate_group_key`, dejando que el modelo invente nombres y formatos distintos en cada ejecución.
2. **Restricciones negativas difusas**: Decir *"no pongas P0 cuando no sea urgente"* es subjetivo; al no definir qué constituye un incidente crítico, palabras como `"hoy"` hacen que el modelo confunda una urgencia individual con una caída global.
3. **Ausencia de contexto de dominio y contratos de código**: No incluye el código de `TriageResult` ni explica la política de SLA (guardia 24/7 para `P0`/`P1` vs. horario hábil para `P2`/`P3`), lo que lleva a pasar por alto brechas críticas de seguridad como la exposición de facturas en `INC-1007`.

### 1.2 Extracción de Contexto Mínimo, *Chain-of-Thought* (`<analysis>`) y *Self-Consistency*
- **Contexto extraído**: Se ejecutó `uv run python -m src.context_audit --symbol classify_incident_report` para aislar únicamente las definiciones de `TriageResult`, `SLA_POLICY_TABLE` y `classify_incident_report` (`1,069 tokens` frente a `8,216` de todo el proyecto).
- **Hallazgos de las 3 corridas independientes (*Self-Consistency*) con razonamiento paso a paso (`<analysis>`)**:
  - **Consenso total en severidades y pares duplicados**: En las 3 corridas independientes hubo acuerdo 3/3 en todas las severidades —degradando `INC-1002` e `INC-1009` a `P2` pese a decir `"hoy"`, y elevando `INC-1007` a `P0` por la vulnerabilidad IDOR en `company_id`— y agrupando siempre `INC-1001` con `INC-1006` y `INC-1003` con `INC-1008`.
  - **Divergencia en el formato de `duplicate_group_key`**: Sin una regla estricta, cada corrida inventó una convención distinta (`payment_gateway_502_credit_card` vs. `payments-gateway-502` vs. `payment-gateway-http-502`, y `perf_reports_historical_slow_query_10k` vs. `reports-history-slow-query-10k` vs. `perf-reports-high-volume-query`). Esto evidenció la necesidad de fijar el formato `<component>:<symptom_category>`.

### 1.3 Refactorización con Rol, Instrucciones Afirmativas, *Few-Shot* y Etiquetas XML
Con base en el consenso anterior, se abrió un «Nuevo chat» y se aplicó este prompt estructurado:

```xml
<role>
Actúa como Ingeniero Principal de Confiabilidad (SRE) y Seguridad en IncidentOps.
</role>

<context>
Refactoriza `TriageResult` en `src/models.py` y `classify_incident_report` en `src/triage_rules.py` usando solo librería estándar de Python.
<!-- Bloque <lsp_context symbol="classify_incident_report"> extraído con context_audit -->
</context>

<domain_rules>
- Severidades (P0/P1 activan guardia 24/7; P2/P3 se atienden L-V 08:00-18:00):
  - P0: Caída global de flujo crítico (ej. HTTP 502 en pagos) o brecha de seguridad/fuga de datos multi-tenant (ej. `company_id`).
  - P1: Degradación severa de infraestructura compartida con riesgo inminente de caída (ej. pool PostgreSQL al 94%).
  - P2: Degradación de rendimiento sin caída (reportes >3s o exportación lenta) o bloqueo de una cuenta individual. Ignora palabras como "hoy" si el impacto es individual.
  - P3: Cambios cosméticos de UI o tareas preventivas en staging.
- Equipos válidos (`recommended_team`): `Backend-Core`, `Platform-SRE`, `Data-DBA` o `Security-IAM`.
- Clave de duplicados (`duplicate_group_key`): Formato exacto `<component>:<symptom_category>` (ej. `payments-gateway:http-502`, `reporting-api:slow-query-10k`).
</domain_rules>

<examples>
  <example>
    Input: INC-1002 ("He intentado ingresar a mi cuenta tres veces y ahora aparece bloqueada. Necesito acceder hoy mismo...")
    <analysis>
      1. Alcance: Cuenta individual bloqueada; servicio global operativo.
      2. Trampa léxica: Dice "hoy", pero no es caída global ni brecha de seguridad.
      3. Salida: `auth-identity:account-lockout` para `Security-IAM`.
    </analysis>
    <output>severity="P2" | component="auth-identity" | recommended_team="Security-IAM" | duplicate_group_key="auth-identity:account-lockout"</output>
  </example>
  <example>
    Input: INC-1001 ("HTTP 502 en gateway de pagos") / INC-1006 ("error 502 al intentar pagar")
    <analysis>
      1. Alcance: Caída global de cobros con tarjeta -> P0.
      2. Duplicados: Mismo componente y síntoma raíz -> `payments-gateway:http-502`.
    </analysis>
    <output>severity="P0" | component="payments-gateway" | recommended_team="Backend-Core" | duplicate_group_key="payments-gateway:http-502"</output>
  </example>
</examples>

<task>
Actualiza `TriageResult` y `classify_incident_report` para clasificar y agrupar correctamente los 10 incidentes de `data/sample_incidents.json`.
</task>
```

**Verificación en terminal (`uv run python -m src.triage_rules`)**:
Al llevar el código a `src/models.py` y `src/triage_rules.py`, la salida en consola confirmó las severidades y componentes corregidos:
- `INC-1002` (`auth-identity`) y `INC-1009` (`reporting-api`) pasaron de `P0` a `P2` al neutralizar la palabra `"hoy"`.
- `INC-1007` (`reporting-api`) subió de `P3` a `P0` por la exposición multi-tenant de facturas vía `company_id`.
- Internamente, `TriageResult` asignó `recommended_team` y `duplicate_group_key` agrupando `INC-1001` e `INC-1006` bajo `payments-gateway:http-502` (`Backend-Core`) y `INC-1003` e `INC-1008` bajo `reporting-api:slow-query-10k` (`Data-DBA`).

---
## 2. Flujo Explorar $\rightarrow$ Destilar $\rightarrow$ Ejecutar en Contexto Limpio (Reto 2: Cálculo de SLA en Horario Hábil y ADR-002)

### 2.1 Exploración de Diseño (Sin Generar Código Aún) y Destilación
- **Contexto extraído**: Se ejecutó `uv run python -m src.context_audit --symbol evaluate_sla_status` para extraer únicamente `SLA_POLICY_TABLE`, los modelos `Incident` / `SLAEvaluation` y `evaluate_sla_status` (`1,218 tokens` frente a `8,794 tokens` de todo el proyecto).
- **Qué exploramos antes de escribir código**:
  1. *Tickets creados fuera de horario*: Si un `P2` entra un viernes a las `18:30` y se revisa el lunes a las `08:30`, el viernes suma `0 minutos`, el fin de semana `0 minutos` y solo cuentan los `30 minutos` del lunes entre `08:00` y `08:30`.
  2. *Tickets creados en fin de semana*: Un `P2` creado el sábado y revisado el domingo lleva `0 minutos` hábiles consumidos.
  3. *Solución simple por días $O(D)$ sin librerías externas*: Descartamos sumar minuto por minuto (innecesariamente lento en tickets largos) y descartamos instalar librerías externas. En su lugar, recorremos día por día desde la fecha de creación hasta la de evaluación ($O(D)$) usando solo `datetime` de Python, y en los días hábiles (`weekday() < 5`) calculamos cuántos minutos caen dentro de `08:00` a `18:00` (máximo 600 min/día).
  4. *Bug en el escalamiento*: Detectamos que el código original tenía `and not is_breached` en `requires_escalation`, lo que apagaba la alerta justo cuando el ticket ya había vencido su SLA.

- **Resumen destilado llevado al chat limpio**:
  > - Descartamos contar minuto a minuto y agregar librerías externas; recorremos día por día $O(D)$ usando solo `datetime`, `time` y `timedelta`.
  > - Para `P0`/`P1` (`operates_24x7=True`) se mantiene el cálculo continuo 24/7.
  > - Para `P2`/`P3` (`operates_24x7=False`) solo suman los minutos que caen dentro de Lunes a Viernes de `08:00` a `18:00` (sábados y domingos suman `0`).
  > - Arreglar `requires_escalation` para que quede en `True` siempre que el ticket no esté resuelto y haya llegado al 75% del SLA o ya esté vencido (`is_breached=True`).
  > - Mantener intacta la firma de `evaluate_sla_status`.

### 2.2 Ejecución con Contexto Curado en Nuevo Chat Limpio (*Context Engineering* $\rightarrow$ ADR-002)
Se abrió un hilo nuevo con el `<lsp_context>` de `evaluate_sla_status`, la plantilla `docs/adr/000-template.md` y el resumen destilado:

```xml
<context>
Necesitamos documentar y resolver el cálculo de SLA en horario hábil en IncidentOps.
Se adjunta el bloque <lsp_context symbol="evaluate_sla_status"> y la plantilla docs/adr/000-template.md.
</context>

<decision_summary>
- Recorrer día por día O(D) entre creación y evaluación usando solo librería estándar (`datetime`, `time`, `timedelta`).
- P0 y P1 (`operates_24x7=True`): cálculo continuo 24/7.
- P2 y P3 (`operates_24x7=False`): sumar solo los minutos dentro de Lunes a Viernes (máx. 600 min/día; fines de semana suman 0).
- Corregir `requires_escalation` para que siga en `True` cuando `is_breached=True` mientras el incidente siga abierto.
</decision_summary>

<constraints>
- Cero dependencias externas.
- No cambiar la firma de `evaluate_sla_status` ni los campos de `SLAEvaluation`.
- Incluir diagrama Mermaid en `docs/adr/002-calculo-sla-horario-habil.md` y validar al menos 5 casos borde con `assert` en `src/sla_calculator.py`.
</constraints>

<task>
1. Redacta `docs/adr/002-calculo-sla-horario-habil.md` siguiendo la plantilla adjunta con un diagrama Mermaid `flowchart TD`.
2. Refactoriza `src/sla_calculator.py` y verifica los casos borde en `_run_demo()`.
</task>
```

### 2.3 Verificación Determinista en Terminal (`uv run python -m src.sla_calculator`)
Al ejecutar `uv run python -m src.sla_calculator` en terminal, los 6 casos borde pasaron sin errores:
- `INC-2001` (`P2`, Vie 17:00 $\rightarrow$ Lun 09:00): `120m` transcurridos (`60m` viernes + `60m` lunes), `Breached: False`, `Escalar: False`.
- `INC-2002` (`P2`, Vie 18:30 fuera de horario $\rightarrow$ Lun 08:30): `30m` transcurridos, `Restante: 450m`.
- `INC-2003` (`P2`, Sáb 11:00 $\rightarrow$ Dom 17:00): `0m` transcurridos.
- `INC-2004` (`P2`, Vie 16:00 $\rightarrow$ Lun 12:00): `360m` transcurridos (75% de 480m) $\rightarrow$ activa `Escalar: True` con `Breached: False`.
- `INC-2004` (`P2`, Vie 16:00 $\rightarrow$ Lun 14:20): `500m` transcurridos $\rightarrow$ `Breached: True` y mantiene `Escalar: True`.
- `INC-2005` (`P0`, Sáb 23:30 $\rightarrow$ Dom 00:45): `75m` transcurridos en modo 24/7 $\rightarrow$ `Breached: True` y `Escalar: True`.

---
## 3. Tipos de Modelos y Matriz de Decisión Arquitectónica

### 3.1 Comparación de Tipos de Modelos
1. **Modelo Rápido / Estándar (modo estándar / Flash)**:
   - Responde casi al instante y funciona muy bien cuando las reglas ya están definidas y la tarea es concreta (por ejemplo, redactar el Markdown del ADR a partir del resumen destilado o generar los casos de prueba con `assert`).
   - Sin embargo, si recibe un prompt ambiguo sin contexto de negocio, tiende a irse por atajos superficiales (como asumir que la palabra `"hoy"` implica urgencia `P0`).
2. **Modelo de Razonamiento Extendido (*Thinking Model*)**:
   - Se toma unos segundos extra para analizar paso a paso antes de responder, lo que marcó la diferencia en las tareas de diagnóstico y diseño:
     - Permitió descubrir que `INC-1007` era una fuga de seguridad entre empresas (`company_id`) aunque no tuviera palabras de alerta.
     - Ayudó a identificar el bug lógico en `requires_escalation` (que se apagaba cuando el ticket ya había vencido) y los casos borde de creación fuera de horario en viernes y fines de semana.
   - En resumen: el modelo de razonamiento fue clave para **explorar, auditar riesgos y descubrir casos borde**, mientras que el modelo rápido bastó para **formatear y generar código sobre decisiones ya tomadas**.

### 3.2 Matriz de Decisión Arquitectónica

| Escenario / Requerimiento | Paradigma Elegido | Justificación Técnica (Determinismo, Costo, Latencia, Riesgo de Alucinación) |
| :--- | :--- | :--- |
| 1. Contabilizar minutos hábiles transcurridos y verificar si un ticket superó el 75% de su SLA | **Código Determinista** | Es un cálculo matemático y de calendario exacto: requiere 100% de precisión, cero riesgo de alucinación, respuesta en microsegundos y costo nulo. |
| 2. Explorar casos borde y redactar un ADR antes de modificar la arquitectura de consultas SQL | **Asistente GenAI en Chat** | Ocurre en tiempo de desarrollo (sin afectar a usuarios finales), donde el valor está en analizar trade-offs, detectar casos borde y estructurar documentación técnica con supervisión humana. |
| 3. Detectar anomalías numéricas en millones de métricas de CPU/RAM por minuto | **ML Clásico** | Para series de tiempo numéricas de alta frecuencia se necesitan modelos ligeros (como Isolation Forest o regresión) que procesan millones de puntos en milisegundos y a bajo costo; usar un LLM sería lento y muy costoso. |
| 4. Clasificar reportes de incidentes redactados en lenguaje natural abierto cuando las reglas deterministas no cubren nuevos patrones | **LLM en Tiempo de Ejecución** | Los usuarios describen fallos nuevos de formas muy distintas (como la fuga por `company_id`), donde los `if/else` por palabras clave fallan. Aquí sí vale la pena el costo y latencia de un LLM acotado a un esquema fijo (`TriageResult`), respaldado por reglas deterministas para los casos conocidos. |

---

## 4. Economía de Tokens y Curaduría de Contexto con `tiktoken` (LSP vs. `grep`/`read` vs. `glob`/`read`)

### 4.1 Medición Empírica en *IncidentOps*

#### A. Símbolo Reto 1: `classify_incident_report`
| Estrategia de Recolección de Contexto | Alcance (Archivos / Nodos) | Caracteres Totales | Tokens (`tiktoken o200k_base`) | % de Reducción vs. Fuerza Bruta |
| :--- | :--- | :---: | :---: | :---: |
| **1. Fuerza Bruta (`glob` + `read` todo)** | 8 archivos (todo el proyecto) | 32,718 | 8,216 tokens | 0% (Línea base) |
| **2. Búsqueda Textual (`grep` + `read` `.py`)** | 2 archivos `.py` donde aparece el símbolo | 5,522 | 1,412 tokens | 82.8% menos tokens |
| **3. Semántica vía LSP (`definition` + `references` + `hover`)** | Solo definición, tipos asociados y referencias | 3,987 | **1,069 tokens** | **87.0% menos tokens** (24.3% menos vs. `grep`+`read`) |

#### B. Símbolo Reto 2: `evaluate_sla_status`
| Estrategia de Recolección de Contexto | Alcance (Archivos / Nodos) | Caracteres Totales | Tokens (`tiktoken o200k_base`) | % de Reducción vs. Fuerza Bruta |
| :--- | :--- | :---: | :---: | :---: |
| **1. Fuerza Bruta (`glob` + `read` todo)** | 8 archivos (todo el proyecto) | 35,090 | 8,794 tokens | 0% (Línea base) |
| **2. Búsqueda Textual (`grep` + `read` `.py`)** | 4 archivos `.py` donde aparece el símbolo | 24,389 | 5,915 tokens | 32.7% menos tokens |
| **3. Semántica vía LSP (`definition` + `references` + `hover`)** | Solo definición, tipos asociados y referencias | 4,746 | **1,218 tokens** | **86.1% menos tokens** (79.4% menos vs. `grep`+`read`) |

- **Análisis del ahorro de tokens**:
  - En el Reto 1 ahorramos **`7,147 tokens`** (`8,216 - 1,069`) y en el Reto 2 ahorramos **`7,576 tokens`** (`8,794 - 1,218`) por turno frente a pegar todo el proyecto.
  - En `evaluate_sla_status`, la búsqueda por texto (`grep + read`) sigue cargando `5,915 tokens` porque esa función aparece mencionada en 4 archivos distintos (incluyendo consultas SQL en `incident_repository.py` y lógica de AST en `context_audit.py` que no tienen nada que ver con el horario hábil). Al usar LSP, recortamos solo la definición, los modelos de datos y las líneas exactas donde se invoca (`1,218 tokens`), evitando llenar la ventana de contexto con código irrelevante.

### 4.2 Comparación de Formatos de Serialización (`--compare-formats`)
Tokens medidos con `tiktoken (o200k_base)` para los mismos 10 incidentes de `data/sample_incidents.json`:

| Formato de Serialización | Caracteres Totales | Tokens (`o200k_base`) | % de Ahorro vs. JSON Indentado |
| :--- | :---: | :---: | :---: |
| **JSON Indentado (`indent=2`)** | 2,942 | 878 tokens | 0% (Línea base) |
| **YAML Equivalente** | 2,579 | 755 tokens | 14.0% menos tokens |
| **JSON Compacto (minified)** | 2,641 | 728 tokens | 17.1% menos tokens |
| **CSV Delimitado por `\|`** | 2,171 | **617 tokens** | **29.7% menos tokens** |

- **Cuándo elegir cada formato en un prompt**:
  - **CSV delimitado (`|`)**: Es el mejor cuando pasamos listas largas de registros con las mismas columnas (como decenas de tickets o logs planos), porque escribe los nombres de los campos una sola vez en la cabecera y ahorra casi **30% de tokens** frente a JSON indentado.
  - **JSON compacto**: Conviene cuando los datos tienen objetos anidados o listas internas variables y necesitamos que el modelo respete una estructura exacta sin gastar tokens en espacios ni saltos de línea.
  - **YAML**: Útil para configuraciones o ejemplos cortos donde prima que sea fácil de leer a simple vista.
