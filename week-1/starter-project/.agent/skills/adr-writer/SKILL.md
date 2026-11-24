---
name: adr-writer
description: >-
  Redacta y valida Architecture Decision Records (ADRs) en `docs/adr/` a partir de
  `docs/adr/000-template.md`. Activar cuando se requiera registrar una decisión arquitectónica
  estructural y difícil de revertir o reemplazar un ADR previo; no activar para criterios
  funcionales/BDD (`spec.md`) ni listas de tareas o archivos (`plan.md`).
---

# ADR Writer

Redacta registros de decisiones arquitectónicas (**ADRs**) inmutables y concisos en `docs/adr/`, reutilizando estrictamente la plantilla oficial `docs/adr/000-template.md`.

## Cuándo crear un ADR

Crea un ADR **únicamente** cuando la decisión sea **estructural y difícil de revertir** (topología de capas, fronteras de módulos, elección de motor de persistencia, protocolo de integración, estrategia de despliegue o concurrencia).

**No** crees un ADR para cambios tácticos, refactorizaciones locales reversibles, requisitos funcionales ni planes de implementación.

## Flujo de trabajo

### 1. Inspeccionar plantilla e historial
1. Lee `docs/adr/000-template.md` y respeta su estructura exacta.
2. Lista `docs/adr/` para asignar el siguiente número consecutivo con formato `NNN-titulo-corto.md` (p. ej. `004-motor-persistencia-relacional.md`).

### 2. Mantener registro inmutable (*append-only*)
- Registra **exactamente 1 sola decisión arquitectónica** por archivo. Si surgen dos decisiones independientes, crea dos ADRs separados.
- **Nunca** edites ni reescribas el cuerpo de un ADR en estado `Aceptado`.
- Para cambiar una decisión previa:
  1. Crea un nuevo ADR (`ADR-YYY`) indicando `**Reemplaza a**: ADR-XXX` (parcial o totalmente).
  2. En `ADR-XXX`, actualiza **únicamente** el metadato `**Estado**: Reemplazado por ADR-YYY`.

### 3. Completar metadatos exactos
Usa únicamente los metadatos definidos en `docs/adr/000-template.md`:
- `**Estado**: Propuesto | Aceptado | Reemplazado por ADR-XXX`
- `**Fecha**: YYYY-MM-DD`
- `**Autor(es)**: [Nombre / Equipo]`
- `**Reemplaza a**: ADR-XXX` *(solo si aplica)*

No agregues `Componentes Afectados` con enlaces a rutas de archivos (se vuelven obsoletos al refactorizar) ni viñetas tácticas de comandos de consola.

### 4. Redactar las 4 secciones

1. **`## 1. Contexto y Problema`**
   - Plantea **una sola decisión estructural**, el contexto técnico o de negocio que la motiva y las restricciones vigentes.
2. **`## 2. Opciones Consideradas`**
   - Compara al menos **2 opciones arquitectónicas reales y viables**.
   - Documenta *Ventajas* y *Desventajas* auténticas para cada opción. Prohibidas las opciones de relleno o *strawmen* diseñadas solo para descartarse.
3. **`## 3. Decisión Arquitectónica`**
   - Indica claramente la opción elegida y **por qué** supera a las alternativas bajo las restricciones actuales.
   - **Diagrama Mermaid (opcional)**: inclúyelo solo si aporta claridad sobre **estructura** (capas, límites de módulos, puertos/adaptadores o topología de componentes). **Nunca** dibujes diagramas de flujo algorítmicos (`if/else`, bucles o pasos procedimentales).
4. **`## 4. Consecuencias y Trade-offs`**
   - **Positivas**: beneficios estructurales (desacoplamiento, portabilidad, escalabilidad, mantenibilidad).
   - **Negativas / Trade-offs**: complejidad asumida, restricciones operativas o costos de mantenimiento reales.

## Prohibiciones explícitas

- **No duplicar `spec.md`**: no incluyas escenarios BDD (`Given / When / Then`), reglas funcionales detalladas ni criterios de aceptación de producto.
- **No duplicar `plan.md`**: no incluyas listas de archivos a crear/modificar, checklists de tareas ni pasos de implementación.
- **No incluir enlaces frágiles ni comandos tácticos**: evita secciones de `Componentes Afectados` apuntando a archivos específicos o comandos `uv` / `pytest` / `docker` en los metadatos o el cuerpo.
- **No mezclar decisiones ni mutar historia**: un archivo = una decisión; correcciones posteriores se registran mediante reemplazo (*append-only*).

## Lista de verificación antes de finalizar

Antes de dar por terminado el ADR, verifica que cumpla todos los puntos:
- [ ] Usa la estructura y metadatos de `docs/adr/000-template.md` (`Estado`, `Fecha`, `Autor(es)`, y `Reemplaza a` / `Reemplazado por` si aplica), sin `Componentes Afectados` ni comandos tácticos.
- [ ] Documenta exactamente **1 decisión estructural** difícil de revertir y preserva el carácter *append-only* de ADRs previos.
- [ ] Compara al menos **2 opciones arquitectónicas reales** con ventajas y desventajas genuinas (cero *strawmen*).
- [ ] Si incluye diagrama Mermaid, es estrictamente **estructural** (sin ramas `if/else` algorítmicas); si no aporta valor estructural, se omite.
- [ ] No duplica criterios funcionales/BDD de `spec.md` ni listas de archivos/tareas de `plan.md`.
