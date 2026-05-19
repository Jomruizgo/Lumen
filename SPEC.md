# SPEC.md — Especificación formal del lenguaje Lumen

> Esta es la **fuente de verdad** sobre la sintaxis y semántica del lenguaje. Cualquier ambigüedad aquí debe escalarse, no asumirse.

---

## 1. Estructura general de un programa

Un programa Lumen consiste en:

```
@lumen <version>          # declaración de versión (obligatoria)
[capabilities ...]        # capacidades requeridas (opcional)
[declarations ...]        # agents, actions, functions
[main block]              # opcional, para scripts simples
```

**Ejemplo mínimo:**

```lumen
@lumen 1.0

action greet(name):
  print "Hello, ${name}"

greet("World")
```

---

## 2. Modos del lenguaje

Los tres modos NO se declaran. Se **infieren** automáticamente por las capacidades usadas (ver ARCHITECTURE.md ADR-003).

El programador puede **forzar** un modo más restrictivo:

```lumen
action sum_numbers(a, b):
  mode: safe        # fuerza safe aunque solo sume números
  return a + b
```

Pero **nunca** un modo menos restrictivo. No puedes declarar `mode: fast` en un programa que usa `transfer.money`.

### Diferencias por modo

| Característica | fast | safe | flow |
|---|---|---|---|
| Audit log | Resumido | Completo por acción | Completo + estado del flow |
| Confirmación humana | Nunca | Obligatoria si declarada | Configurable |
| Verbose syntax | Permitida sintaxis densa | Sintaxis explícita obligatoria | Mixta |
| Resolución de ambigüedad | Inferida | Explícita obligatoria | Por bloque |
| Reversibilidad | Best-effort | Declarada obligatoriamente | Por acción |

---

## 3. Sintaxis formal (EBNF)

```ebnf
program        = version_decl, { top_level } ;

version_decl   = "@lumen", number, ".", number ;

top_level      = capability_decl
               | agent_decl
               | action_decl
               | function_decl
               | import_decl
               | main_statement ;

capability_decl = "use", capability_path, [ "as", identifier ] ;
capability_path = identifier, { ".", identifier } ;

agent_decl     = "agent", identifier, ":", agent_body ;
agent_body     = { watch_clause | on_clause | schedule_clause | config_clause } ;
watch_clause   = "watch", ":", expression ;
on_clause      = "on", pattern, "->", block ;
schedule_clause = "schedule", ":", schedule_expr ;
config_clause  = identifier, ":", expression ;

action_decl    = "action", identifier, "(", [ params ], ")", ":", action_body ;
action_body    = { requires_clause | execute_clause | reversible_clause | audit_clause } ;
requires_clause = "requires", ":", expression ;
execute_clause = "execute", ":", block ;
reversible_clause = "reversible", ":", boolean | duration ;
audit_clause   = "audit", ":", audit_level ;

function_decl  = "fn", identifier, "(", [ params ], ")", [ "->", type ], ":", block ;

params         = param, { ",", param } ;
param          = identifier, [ ":", type ], [ "=", expression ] ;

type           = primitive_type | parametrized_type | union_type ;
primitive_type = "text" | "number" | "time" | "boolean" | "any" ;
parametrized_type = identifier, "<", type, { ",", type }, ">" ;
union_type     = type, "|", type ;

block          = INDENT, { statement }, DEDENT ;

statement      = pipeline
               | assignment
               | if_statement
               | match_statement
               | for_statement
               | resolve_block
               | return_statement
               | expression ;

pipeline       = expression, { "|", expression } ;

assignment     = identifier, "=", expression, [ "because", string ] ;

resolve_block  = "resolve", "(", expression, ")", "{", resolve_strategies, "}" ;
resolve_strategies = { strategy_clause } ;
strategy_clause = strategy_name, ":", block_or_expression ;
strategy_name  = "high_confidence" | "ask_user" | "use_context"
               | "infer_from_history" | "fail_safe" | "ambiguous" | "unknown" ;

if_statement   = "if", expression, ":", block, [ "else", ":", block ] ;

match_statement = "match", expression, ":", { match_arm } ;
match_arm      = pattern, "->", block_or_expression ;

for_statement  = "for", identifier, "in", expression, ":", block ;

return_statement = "return", [ expression ] ;

expression     = literal
               | identifier
               | function_call
               | binary_op
               | string_interpolation
               | capability_call ;

capability_call = capability_path, "(", [ args ], ")" ;

string_interpolation = '"', { char | "${", expression, "}" }, '"' ;

literal        = number_literal | string_literal | boolean_literal | time_literal | money_literal ;

money_literal  = currency_symbol, number, [ currency_code ] ;
time_literal   = number, time_unit ;
time_unit      = "s" | "min" | "h" | "d" | "w" | "y" ;

duration       = number, "h" | number, "d" | number, "w" ;
```

---

## 4. Sistema de tipos

### 4.1 Tipos primitivos

| Tipo | Descripción | Ejemplo |
|---|---|---|
| `text` | Cadena unicode | `"hola"` |
| `number` | Entero o decimal | `42`, `3.14` |
| `boolean` | true / false | `true` |
| `time` | Instante o duración | `2026-05-18T10:00`, `5min` |
| `any` | Cualquier tipo (escape hatch) | — |

### 4.2 Tipos semánticos (no solo estructurales)

| Tipo | Validación | Ejemplo |
|---|---|---|
| `Money<currency>` | Monto + moneda, no se suma con otras monedas | `$100 USD`, `€50 EUR` |
| `EmailAddress` | Validación RFC 5322 | `"x@y.com"` |
| `Url` | URL válida con esquema | `"https://..."` |
| `Phone<region>` | Validado por región | `"+1234..."` |
| `Path` | Path de filesystem normalizado | `"/home/x"` |
| `Entity<kind>` | Referencia a una entidad resuelta | `Entity<Person>` |

### 4.3 Tipos paramétricos

| Tipo | Significado |
|---|---|
| `Maybe<T>` | Valor que puede ser `T` o requerir resolución |
| `Pending<T>` | Valor que espera aprobación humana antes de ser `T` |
| `Reversible<T>` | Resultado de una operación reversible |
| `Irreversible<T>` | Resultado de una operación NO reversible |
| `List<T>` | Lista homogénea |
| `Map<K, V>` | Diccionario tipado |
| `Confidence<T>` | Valor con score 0.0-1.0 |

### 4.4 Tipos unión

```lumen
fn parse_response(r) -> Number | Text:
  ...
```

### 4.5 Inferencia

El tipo se infiere por defecto. Anotaciones obligatorias solo en:
- Firmas de `action` con modo `safe`
- Parámetros de `fn` exportadas
- Valores que cruzan boundaries de capability

---

## 5. Capacidades (capabilities)

### 5.1 Declaración

```lumen
use comm.email
use sensitive.transfer
use data.search as search
```

**Regla:** Solo capacidades declaradas pueden usarse. Usar una no declarada es error `LMN-0001`.

### 5.2 Catálogo de capacidades stdlib v1

#### comm.*
- `read.email(filter)` → `List<Email>`
- `send.email(to, subject, body)` → `Reversible<Sent>`
- `summarize.email(email, max_lines)` → `Text`
- `send.message(channel, recipient, text)` → `Reversible<Sent>`
- `notify.user(text, priority)` → `Reversible<Notified>`
- `speak.text(text)` → `Spoken`
- `listen.user(timeout)` → `Text`

#### time.*
- `read.calendar(range)` → `List<Event>`
- `create.event(title, start, end, attendees)` → `Reversible<Event>`
- `find.freetime(duration, range)` → `List<TimeSlot>`
- `now()` → `time`
- `wait(duration)` → unit

#### data.*
- `read.file(path)` → `Text | Bytes`
- `write.file(path, content)` → `Reversible<Written>`
- `parse.document(path)` → `StructuredDoc`
- `search.semantic(query, corpus)` → `List<Result>`
- `extract.entities(text, types)` → `List<Entity>`

#### sensitive.*
- `transfer.money(from, to, amount)` → `Pending<Reversible<Transfer>>`
- `delete.permanent(path)` → `Pending<Irreversible<Deleted>>`
- `deploy.production(system, version)` → `Pending<Reversible<Deployed>>`

#### cli.*
- `run(command, args)` → `Output`
- `pipe(commands)` → `Output`
- `wrap(binary_path)` → `Capability`

#### web.*
- `fetch.url(url)` → `Response`
- `post.url(url, body)` → `Reversible<Response>`
- `serve.webhook(port, handler)` → `Server`

#### llm.*
- `ask(prompt, context)` → `Text`
- `classify(input, categories)` → `Confidence<Category>`
- `extract(text, schema)` → `Structured`

---

## 6. Resolución de ambigüedad

### 6.1 Sintaxis básica

```lumen
recipient = resolve("el cliente principal") {
  high_confidence: use_context(crm.last_interaction)
  ambiguous: ask_user("¿A cuál cliente te refieres?")
  unknown: fail_safe()
}
```

### 6.2 Estrategias

| Estrategia | Comportamiento |
|---|---|
| `high_confidence` | Si confianza ≥ 0.9, ejecuta el bloque |
| `ambiguous` | Si confianza entre 0.5 y 0.9 |
| `unknown` | Si confianza < 0.5 |
| `ask_user` | Escala al humano con opciones |
| `use_context(...)` | Usa el valor pasado como contexto |
| `infer_from_history` | Usa el audit log para inferir |
| `fail_safe` | Aborta el programa con error |

### 6.3 Reglas

- En modo `safe`, todo `resolve` debe tener al menos `ambiguous` y `unknown`
- En modo `fast`, el compilador inserta `unknown: fail_safe()` automáticamente
- La confianza la determina el LLM resolver (ver ARCHITECTURE.md ADR-007)

---

## 7. Reversibilidad

### 7.1 Declaración en acciones

```lumen
action pay_supplier(supplier, amount):
  requires: amount > 0
  reversible: 24h        # ventana de undo
  audit: full
  execute:
    transfer.money(from=company_account, to=supplier, amount)
```

### 7.2 Valores posibles para `reversible:`

| Valor | Significado |
|---|---|
| `true` | Reversible sin límite de tiempo |
| `false` | Irreversible (debe ser explícito) |
| `<duration>` | Reversible dentro de la ventana (ej: `24h`, `7d`) |
| `conditional(<expr>)` | Reversible si expresión es true |

### 7.3 Composición en pipelines

```lumen
process_invoice
  | parse.document          # reversible: true
  | extract.amount          # reversible: true
  | transfer.money          # reversible: 24h
  | send.confirmation       # reversible: false
```

**Regla:** La reversibilidad del pipeline es la del paso menos reversible. El pipeline completo es `reversible: false`.

### 7.4 Undo

```lumen
undo(action_id="abc-123")
```

Solo funciona si la acción es reversible y está dentro de la ventana.

---

## 8. Auditoría

### 8.1 Niveles

```lumen
action x:
  audit: full       # Todo: decisiones, ejecución, resolución
  # audit: minimal  # Solo ejecución
  # audit: silent   # Nada (solo permitido en modo fast)
```

### 8.2 Default por modo

- `fast`: `minimal`
- `safe`: `full` (no se puede bajar)
- `flow`: `full`

### 8.3 Acceso al log desde el programa

```lumen
history = audit.query(
  action="transfer.money",
  since=7.days.ago,
  status="completed"
)
```

---

## 9. Agents (en modo flow)

### 9.1 Estructura

```lumen
agent inbox_monitor:
  watch: comm.email
  
  on email(from=customer, priority>0.7):
    summary = summarize.email(email, max_lines=3)
    notify.user(summary, priority="high")
  
  on email(from=spam_list):
    # ignorar
    pass
  
  config:
    escalation: webhook(url="https://...")
    retry_on_error: 3
```

### 9.2 Lifecycle

- `agent start <name>` → inicia el agent (subprocess persistente)
- `agent stop <name>` → detiene
- `agent status <name>` → estado actual
- `agent logs <name>` → audit log filtrado

### 9.3 Estado del agent

Los agents pueden mantener estado entre eventos:

```lumen
agent inbox_monitor:
  state:
    seen_threads: List<Text> = []
  
  on email(from=customer):
    if email.thread_id not in state.seen_threads:
      state.seen_threads.append(email.thread_id)
      ...
```

El estado se persiste en `~/.lumen/agents/<name>/state.json`.

---

## 10. Pipelines

### 10.1 Sintaxis

```lumen
data
  | transform1
  | transform2(arg)
  | filter(predicate)
  | sink
```

### 10.2 Reglas

- El output de cada paso es input del siguiente
- Errores se propagan como valores (no excepciones)
- Si un paso retorna `Maybe<T>`, debe haber resolución antes de continuar
- Pipelines son lazy por default; se ejecutan al alcanzar un sink

### 10.3 Sinks

Acciones que disparan ejecución:
- Asignación a variable
- Llamada que retorna `unit`
- Función `collect()`
- Función `execute()`

---

## 11. Contexto y `because`

### 11.1 Annotations de contexto

Cualquier valor mágico debe tener contexto:

```lumen
tax_rate = 0.16 because "IVA México 2026"
deadline = 2026-12-31 because "cierre fiscal"
```

### 11.2 En modo safe es obligatorio

Constantes numéricas o strings sin `because` en modo safe → error `LMN-0020`.

---

## 12. Errores como valores

### 12.1 Tipos

Todo lo que puede fallar retorna `Result<T, E>`:

```lumen
result = fetch.url("https://...")

match result:
  ok(response) -> process(response)
  fail(reason) -> 
    notify.user("Falló: ${reason}")
    fail_safe()
```

### 12.2 Sintaxis corta

```lumen
# Propagar error con `?`
data = fetch.url("...")?
        | parse.json?
        | extract.field("user")?
```

Si cualquier paso falla, el `?` propaga el error hacia arriba.

---

## 13. Imports

```lumen
import "./helpers.lumen"
import math from std
import comm.email as mail
```

- Imports relativos con `./`
- Imports de stdlib con `from std`
- Aliasing con `as`

---

## 14. Comentarios

```lumen
# Comentario de línea

#: Doc comment (extraído por `lumen explain`)
action important():
  ...
```

---

## 15. Reglas léxicas

- Identificadores: `[a-zA-Z_][a-zA-Z0-9_]*`
- Keywords reservadas: `action`, `agent`, `fn`, `use`, `import`, `if`, `else`, `match`, `for`, `return`, `resolve`, `because`, `mode`, `requires`, `execute`, `reversible`, `audit`, `watch`, `on`, `state`, `config`, `schedule`, `true`, `false`
- Indentación: 2 espacios obligatorio (no tabs)
- Strings: con interpolación `${...}`
- Números con unidades: `5min`, `100USD`, `2.5h`

---

## 16. Catálogo de errores

Ver `docs/errors.md` para catálogo completo. Estructura:

```
LMN-0001  CapabilityNotDeclared      Capacidad usada sin declarar
LMN-0002  UnresolvedAmbiguity        resolve sin estrategia para confianza obtenida
LMN-0003  IrreversibleNotDeclared    Operación irreversible sin declaración
LMN-0010  SyntaxError                Error de parseo
LMN-0011  IndentationError           Indentación inconsistente
LMN-0020  ConstantWithoutContext     Modo safe sin `because`
LMN-0030  TypeMismatch               Error de tipo
LMN-0040  ModeViolation              Mezcla incorrecta de modos
LMN-0050  EscalationTimeout          Humano no respondió en tiempo
LMN-0060  UndoOutsideWindow          Undo fuera de ventana de tiempo
LMN-0070  UndoChainBroken            Cadena de undo no se pudo completar
```

---

## Siguiente paso

Lee `TASKS.md` para tu track asignado, y `EXAMPLES.md` para programas que sirven como tests de aceptación.
