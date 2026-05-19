# Ejemplos de Lumen

Estos 15 programas son los casos de aceptación canónicos del lenguaje. Sirven como referencia de sintaxis, modos y comportamiento esperado.

## Índice

| Archivo | Modo | Descripción |
|---|---|---|
| `01_hello.lumen` | fast | Hello World mínimo |
| `02_function.lumen` | fast | Función con tipos inferidos |
| `03_email_read.lumen` | fast | Lectura de email + filtro por prioridad |
| `04_payment.lumen` | safe | Pago con resolución de ambigüedad y undo |
| `05_inbox_agent.lumen` | flow | Agent de monitoreo con estado |
| `06_pipeline_errors.lumen` | fast | Pipeline con propagación de errores |
| `07_resolution.lumen` | safe | Resolución de equipo + envío masivo |
| `08_cli_wrap.lumen` | safe | Wrapping de CLI (ffmpeg) |
| `09_semantic_search.lumen` | fast | Búsqueda semántica en documentos |
| `10_webhook_approval.lumen` | safe | Transferencia con aprobación via webhook |
| `11_undo.lumen` | safe | Listar y deshacer transferencias recientes |
| `12_morning_brief.lumen` | safe | Resumen matutino con LLM |
| `13_money.lumen` | fast | Tipos Money y error de currency mixta |
| `14_constants.lumen` | safe | Constantes con `because` obligatorio |
| `15_scheduled_agent.lumen` | flow | Agent con schedule cron |

## Descripción detallada

### 01_hello.lumen — Hello World

El programa más simple posible. Demuestra que la declaración de versión es obligatoria y que `print` es un builtin disponible en modo fast sin ninguna capacidad declarada.

**Modo detectado:** fast  
**Test negativo:** Quitar `@lumen 1.0` produce `LMN-0100 MissingVersionDeclaration`.

---

### 02_function.lumen — Función simple

Define `fn add(a, b)` sin anotaciones de tipo. El compilador infiere `number + number -> number`. Demuestra que las anotaciones son opcionales en modo fast.

**Modo detectado:** fast  
**Tipos inferidos:** `a: number`, `b: number`, retorno `number`.

---

### 03_email_read.lumen — Lectura de email

Usa `comm.email` para leer correos y los filtra con un pipeline inline. Demuestra que la lectura es modo fast (no modifica nada). El filtro usa una lambda `e -> e.priority > 0.7`.

**Modo detectado:** fast  
**Test negativo:** Omitir `use comm.email` produce `LMN-0001 CapabilityNotDeclared`.

---

### 04_payment.lumen — Pago con aprobación

Demuestra el modo safe completo: `reversible: 24h`, `audit: full`, bloque `resolve` con tres estrategias, y llamada a `transfer.money`. Requiere aprobación humana antes de ejecutar.

**Modo detectado:** safe  
**Test negativo 1:** Quitar `reversible: 24h` produce `LMN-0003 IrreversibleNotDeclared`.  
**Test negativo 2:** Declarar `mode: fast` produce `LMN-0040 ModeViolation`.

---

### 05_inbox_agent.lumen — Agent de monitoreo

Agent en modo flow con estado persistente (`seen_threads`), cláusula `watch`, cláusula `on` con guardia `where`, y configuración de escalación. Se ejecuta como proceso persistente.

**Modo detectado:** flow  
**Estado persistido en:** `~/.lumen/agents/inbox_monitor/state.json`

---

### 06_pipeline_errors.lumen — Pipeline con errores

Función que retorna `Map | Error`. Usa el operador `?` para propagar errores en el pipeline. El `match` en el caller maneja `ok` y `fail`. Demuestra que los errores son valores, no excepciones.

**Modo detectado:** fast  
**El pipeline es lazy:** se ejecuta al asignar `data`.

---

### 07_resolution.lumen — Resolución con estrategias

Action con `reversible: false` (lo que fuerza modo safe) y bloque `resolve` con `ask_user` que incluye opciones. Itera sobre miembros del equipo resuelto.

**Modo detectado:** safe  
**Nota:** `reversible: false` debe declararse explícitamente; omitirlo produce `LMN-0003`.

---

### 08_cli_wrap.lumen — CLI wrapping

Wrappea `ffmpeg` con `cli.run`. Captura el resultado con `match`. Demuestra el patrón de integración con herramientas externas sin perder el modelo de seguridad.

**Modo detectado:** safe  
**`fail_safe(reason=stderr)`:** escala con contexto claro.

---

### 09_semantic_search.lumen — Búsqueda semántica

Pipeline de búsqueda semántica con `sort_by` y `take`. No modifica datos, por eso es modo fast. Demuestra acceso a campos con sintaxis de punto en el sort.

**Modo detectado:** fast  
**El corpus se indexa con cache** para búsquedas repetidas.

---

### 10_webhook_approval.lumen — Aprobación via webhook

Escalación a webhook externo con timeout de 300s. Si no hay respuesta en tiempo, `LMN-0050 EscalationTimeout`. El `because` en `transfer.money` documenta el motivo de la transacción en el audit log.

**Modo detectado:** safe  
**Ventana de undo:** 1 hora desde la ejecución.

---

### 11_undo.lumen — Deshacer acción

Consulta el audit log con `audit.query`, presenta los resultados, y ejecuta `undo(action_id=...)` sobre la selección del usuario. Demuestra la integración entre audit log y sistema de undo.

**Modo detectado:** safe  
**Solo funciona** si la acción está dentro de su ventana de reversibilidad.

---

### 12_morning_brief.lumen — Resumen matutino

Combina email, calendario y LLM en un solo action. Demuestra cómo pasar contexto estructurado a `llm.ask`. La notificación al usuario es reversible dentro de la sesión.

**Modo detectado:** safe  
**Cuatro capacidades:** `comm.email`, `comm.notify`, `time.calendar`, `llm.ask`.

---

### 13_money.lumen — Tipos Money

Demuestra que `$100 USD + $50 USD` compila y produce `$150 USD`, pero `$100 USD + €50 EUR` produce `LMN-0030 TypeMismatch`. La línea inválida está comentada para que el archivo compile.

**Modo detectado:** fast  
**Mensaje de error:** "Cannot add Money<USD> and Money<EUR>. Use convert() explicitly."

---

### 14_constants.lumen — Constantes con `because`

En modo safe (forzado por `sensitive.transfer`), toda constante numérica o string literal "mágica" requiere `because`. Demuestra que `tax_rate = 0.16` y `deadline = 2026-12-31` son válidas con contexto.

**Modo detectado:** safe  
**Test negativo:** Quitar cualquier `because` produce `LMN-0020 ConstantWithoutContext`.

---

### 15_scheduled_agent.lumen — Agent con cron

Agent con `schedule` en formato cron. La cláusula `on tick` se dispara en cada ejecución programada. Demuestra el patrón de recordatorio diario sin estado (stateless).

**Modo detectado:** flow  
**Schedule:** `"0 8 * * *"` = 8am todos los días.
