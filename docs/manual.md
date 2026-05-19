# Manual del Lenguaje Lumen

> Versión 1.0 — Referencia completa para desarrolladores y LLMs que generan código Lumen.

---

## 1. Inicio rápido

### Programa mínimo

```lumen
@lumen 1.0

print "Hello, World"
```

Toda regla del lenguaje empieza desde aquí. La declaración `@lumen 1.0` es obligatoria y debe ser la primera línea. Omitirla produce `LMN-0100 MissingVersionDeclaration`.

### Primer programa útil

```lumen
@lumen 1.0
use comm.email

emails = read.email(since="yesterday")
urgent = emails | filter(e -> e.priority > 0.7)

print "Tienes ${urgent.length} correos urgentes"
```

Observa que:
- `use comm.email` declara la capacidad antes de usarla
- `read.email` retorna una lista
- `|` es el operador de pipeline
- `"${...}"` es interpolación de string
- No hay tipos explícitos — se infieren

---

## 2. Modos del lenguaje

Lumen tiene tres modos que se **infieren automáticamente** según las capacidades usadas. No se declaran; el compilador los detecta.

### fast

El modo predeterminado. Para scripts de lectura, cálculo y búsqueda.

- Sin confirmación humana
- Audit log mínimo
- Reversibilidad best-effort

```lumen
@lumen 1.0
use comm.email

emails = read.email(since="yesterday")
print "Total: ${emails.length}"
```

### safe

Se activa cuando se usan capacidades de `sensitive.*`, o cuando una acción tiene `reversible: false` o `audit: full`.

- Confirmación humana obligatoria (si la acción lo declara)
- Audit log completo
- `because` obligatorio en constantes mágicas

```lumen
@lumen 1.0
use sensitive.transfer

action pay(supplier, amount):
  requires: amount > 0
  reversible: 24h
  audit: full
  execute:
    transfer.money(from=company, to=supplier, amount=amount)
```

### flow

Se activa cuando el programa define un `agent`. Modo de larga duración.

- Proceso persistente
- Estado entre eventos
- Escalación configurable

```lumen
@lumen 1.0
use comm.email

agent inbox_monitor:
  watch: read.email(filter={unread: true})
  
  on email(e) where e.priority > 0.7:
    notify.user("Urgente: ${e.subject}", priority="high")
  
  config:
    escalation: cli
    poll_interval: 5min
```

### Forzar un modo más restrictivo

```lumen
fn sum(a, b):
  mode: safe  # fuerza safe aunque solo sume números
  return a + b
```

**No se puede forzar un modo menos restrictivo.** Declarar `mode: fast` en un contexto que usa `sensitive.*` produce `LMN-0040 ModeViolation`.

---

## 3. Sintaxis base

### Declaración de versión

```lumen
@lumen 1.0
```

Obligatoria, primera línea, formato exacto.

### Declaración de capacidades

```lumen
use comm.email
use sensitive.transfer
use data.search as search  # alias opcional
```

Deben ir después de la versión y antes de las declaraciones.

### Comentarios

```lumen
# Comentario de línea (ignorado por el compilador)

#: Doc comment (extraído por lumen explain)
fn documented():
  return 42
```

### Asignación

```lumen
x = 42
name = "Lumen"
flag = true
amount = $100 USD
duration = 5min
```

### Asignación con contexto

```lumen
# En modo safe, constantes numéricas o strings "mágicos" requieren because
tax_rate = 0.16 because "IVA México 2026, ley vigente"
deadline = 2026-12-31 because "Cierre fiscal anual"
```

### Indentación

- **2 espacios obligatorio** (no tabs)
- Cada bloque aumenta 2 espacios
- El compilador rechaza tabs: `LMN-0011 IndentationError`

---

## 4. Tipos del sistema

### Tipos primitivos

| Tipo | Descripción | Ejemplo |
|---|---|---|
| `text` | Cadena unicode | `"hola"` |
| `number` | Entero o decimal | `42`, `3.14` |
| `boolean` | true / false | `true` |
| `time` | Instante o duración | `5min`, `2h`, `7d` |
| `any` | Escape hatch sin tipo | — |

### Tipos semánticos

| Tipo | Validación | Ejemplo |
|---|---|---|
| `Money<currency>` | Monto + moneda ISO 4217 | `$100 USD`, `€50 EUR` |
| `EmailAddress` | Validación RFC 5322 | `"x@y.com"` |
| `Url` | URL válida con esquema | `"https://..."` |
| `Path` | Path de filesystem | `"/home/user"` |
| `Entity<kind>` | Referencia resuelta | `Entity<Person>` |

**Regla de Money:** no se pueden sumar montos de distinta currency.

```lumen
# OK
total = $100 USD + $50 USD   # Money<USD>

# ERROR: LMN-0030 TypeMismatch
total = $100 USD + €50 EUR   # Cannot add Money<USD> and Money<EUR>
```

### Tipos paramétricos

| Tipo | Significado |
|---|---|
| `Maybe<T>` | Valor que puede requerir resolución |
| `Pending<T>` | Espera aprobación humana |
| `Reversible<T>` | Resultado de operación reversible |
| `Irreversible<T>` | Resultado de operación NO reversible |
| `List<T>` | Lista homogénea |
| `Map<K, V>` | Diccionario tipado |
| `Confidence<T>` | Valor con score 0.0-1.0 |

### Tipos unión

```lumen
fn parse(r) -> Number | Text | Error:
  return r
```

### Inferencia de tipos

El compilador infiere tipos por defecto. Las anotaciones son obligatorias solo en:
- Firmas de `action` con modo safe
- Parámetros de `fn` exportadas
- Valores que cruzan boundaries de capability

---

## 5. Capacidades

### Declaración

```lumen
use comm.email
use sensitive.transfer
use data.search as search
```

**Usar una capacidad sin declararla produce `LMN-0001 CapabilityNotDeclared`.**

### Catálogo completo — stdlib v1

#### comm.*

| Función | Firma | Descripción |
|---|---|---|
| `read.email(filter)` | `-> List<Email>` | Lee emails |
| `send.email(to, subject, body)` | `-> Reversible<Sent>` | Envía email |
| `summarize.email(email, max_lines)` | `-> text` | Resume email con LLM |
| `send.message(channel, recipient, text)` | `-> Reversible<Sent>` | Mensaje de chat |
| `notify.user(text, priority)` | `-> Reversible<Notified>` | Notificación al usuario |
| `speak.text(text)` | `-> Spoken` | Síntesis de voz |
| `listen.user(timeout?)` | `-> text` | Lee input del usuario |

#### time.*

| Función | Firma | Descripción |
|---|---|---|
| `read.calendar(range)` | `-> List<Event>` | Lee eventos |
| `create.event(title, start, end, attendees)` | `-> Reversible<Event>` | Crea evento |
| `find.freetime(duration, range)` | `-> List<TimeSlot>` | Busca tiempo libre |
| `now()` | `-> time` | Tiempo actual |
| `wait(duration)` | `-> unit` | Pausa |

#### data.*

| Función | Firma | Descripción |
|---|---|---|
| `read.file(path)` | `-> text \| Bytes` | Lee archivo |
| `write.file(path, content)` | `-> Reversible<Written>` | Escribe archivo |
| `parse.document(path)` | `-> StructuredDoc` | Parsea documento |
| `search.semantic(query, corpus)` | `-> List<Result>` | Búsqueda semántica |
| `extract.entities(text, types)` | `-> List<Entity>` | Extrae entidades |

#### sensitive.*

| Función | Firma | Descripción |
|---|---|---|
| `transfer.money(from, to, amount)` | `-> Pending<Reversible<Transfer>>` | Transferencia bancaria |
| `delete.permanent(path)` | `-> Pending<Irreversible<Deleted>>` | Borrado permanente |
| `deploy.production(system, version)` | `-> Pending<Reversible<Deployed>>` | Deploy a producción |

#### cli.*

| Función | Firma | Descripción |
|---|---|---|
| `cli.run(command, args)` | `-> Output` | Ejecuta CLI |
| `cli.pipe(commands)` | `-> Output` | Pipe de comandos |
| `cli.wrap(binary_path)` | `-> Capability` | Wrappea binario |

#### web.*

| Función | Firma | Descripción |
|---|---|---|
| `fetch.url(url)` | `-> Response` | GET HTTP |
| `post.url(url, body)` | `-> Reversible<Response>` | POST HTTP |
| `serve.webhook(port, handler)` | `-> Server` | Servidor webhook |

#### llm.*

| Función | Firma | Descripción |
|---|---|---|
| `llm.ask(prompt, context?)` | `-> text` | Consulta al LLM |
| `llm.classify(input, categories)` | `-> Confidence<Category>` | Clasificación |
| `llm.extract(text, schema)` | `-> Structured` | Extracción estructurada |

---

## 6. Actions

Las actions son el mecanismo principal para operaciones de efecto con control de seguridad.

### Estructura completa

```lumen
action nombre(param1, param2):
  requires: <expresión boolean>    # precondición
  reversible: <valor>              # ventana de undo
  audit: <nivel>                   # nivel de log
  escalation: <mecanismo>          # aprobación humana (opcional)
  execute:                         # bloque de ejecución
    <statements>
```

### Cláusulas

#### requires

Precondición que debe cumplirse antes de ejecutar:

```lumen
requires: amount > 0
requires: user.role == "admin"
```

Si no se cumple, la action falla con error descriptivo antes de ejecutar nada.

#### reversible

| Valor | Significado |
|---|---|
| `true` | Reversible sin límite de tiempo |
| `false` | Irreversible (declaración explícita obligatoria) |
| `24h`, `1h`, `7d` | Ventana de tiempo para undo |
| `conditional(expr)` | Reversible si expresión es true |

**Omitir `reversible:` en modo safe produce `LMN-0003 IrreversibleNotDeclared`.**

#### audit

| Nivel | Descripción |
|---|---|
| `full` | Decisiones + ejecución + resolución |
| `minimal` | Solo ejecución |
| `silent` | Nada (solo en modo fast) |

#### escalation

Mecanismo de aprobación humana:

```lumen
escalation: cli                                  # pregunta en terminal
escalation: webhook(url="https://...", timeout=300s)  # POST al webhook
```

#### execute

Bloque de ejecución con todos los statements disponibles.

### Ejemplo completo

```lumen
@lumen 1.0
use sensitive.transfer

action pay_supplier(supplier_name, amount):
  requires: amount > 0
  reversible: 24h
  audit: full
  execute:
    supplier = resolve(supplier_name) {
      high_confidence: use_context(crm.suppliers)
      ambiguous: ask_user("¿Cuál proveedor?")
      unknown: fail_safe()
    }
    
    transfer.money(
      from=company_account,
      to=supplier.account,
      amount=amount
    )

pay_supplier("Pedro García", $1000 USD)
```

---

## 7. Functions

Las functions son bloques de código reutilizable sin efectos secundarios de seguridad.

### Sintaxis

```lumen
fn nombre(param1, param2) -> TipoRetorno:
  <statements>
  return valor
```

### Sin anotaciones (fast mode)

```lumen
fn add(a, b):
  return a + b

result = add(2, 3)  # result: number
```

### Con anotaciones

```lumen
fn process(name: text, count: number) -> boolean:
  return count > 0
```

### Con tipo unión

```lumen
fn get_data(id) -> Map | Error:
  result = fetch.url("https://api.example.com/users/${id}")?
    | parse.json?
  return result
```

### Forzar modo en función

```lumen
fn sum(a, b):
  mode: safe  # más restrictivo que lo necesario
  return a + b
```

---

## 8. Agents

Los agents son procesos persistentes que reaccionan a eventos. Solo en modo flow.

### Estructura

```lumen
agent nombre:
  watch: <expresión>         # fuente de eventos (o schedule)
  schedule: "<cron>"         # alternativa a watch
  
  state:                     # estado persistente (opcional)
    variable: Tipo = valor_inicial
  
  on patron(binding) where condicion:
    <statements>
  
  config:
    escalation: cli | webhook(...)
    poll_interval: <duración>
    retry_on_error: <número>
```

### Agent con watch

```lumen
@lumen 1.0
use comm.email
use comm.notify

agent inbox_monitor:
  watch: read.email(filter={unread: true})
  
  state:
    seen_threads: List<Text> = []
  
  on email(e) where e.priority > 0.7:
    if e.thread_id in state.seen_threads:
      pass
    else:
      state.seen_threads.append(e.thread_id)
      summary = summarize.email(e, max_lines=3)
      notify.user(summary, priority="high")
  
  config:
    escalation: cli
    poll_interval: 5min
```

### Agent con schedule (cron)

```lumen
@lumen 1.0
use comm.notify
use time.calendar

agent daily_reminder:
  schedule: "0 8 * * *"  # 8am cada día
  
  on tick:
    events = read.calendar(range="today")
    if events.length > 0:
      notify.user("Hoy: ${events.length} eventos", priority="normal")
  
  config:
    escalation: cli
```

### Ciclo de vida del agent

```bash
lumen agent start inbox_monitor   # inicia como subprocess
lumen agent stop inbox_monitor    # detiene
lumen agent status inbox_monitor  # estado
lumen agent logs inbox_monitor    # audit log filtrado
```

El estado se persiste en `~/.lumen/agents/<nombre>/state.json`.

---

## 9. Pipelines

### Sintaxis básica

```lumen
resultado = fuente | paso1 | paso2(arg) | sink
```

### En múltiples líneas

```lumen
resultado = search.semantic(query="test", corpus="~/Docs/")
  | sort_by(.relevance, descending)
  | filter(r -> r.relevance > 0.5)
  | take(10)
```

### Lambdas en pipelines

```lumen
urgent = emails | filter(e -> e.priority > 0.7)
names = users | map(u -> u.name)
```

### Propagación de errores con `?`

```lumen
fn get_user(id) -> Map | Error:
  result = fetch.url("https://api.example.com/users/${id}")?
    | parse.json?
    | extract.field("data")?
  return result
```

Si cualquier paso falla, `?` propaga el error hacia arriba sin ejecutar el resto.

### Reglas de reversibilidad en pipelines

La reversibilidad del pipeline es la del paso **menos** reversible:

```lumen
process_invoice
  | parse.document   # reversible: true
  | extract.amount   # reversible: true
  | transfer.money   # reversible: 24h
  | send.email       # reversible: false   ← limita todo el pipeline
```

El pipeline completo es `reversible: false`.

### Sinks (disparan ejecución)

- Asignación a variable
- Llamada que retorna `unit`
- `collect()`
- `execute()`

Los pipelines son **lazy** hasta alcanzar un sink.

---

## 10. Resolución de ambigüedad

Cuando una entidad puede ser ambigua, Lumen fuerza la resolución explícita.

### Sintaxis

```lumen
entity = resolve(expresion_ambigua) {
  high_confidence: <acción>   # confianza >= 0.9
  ambiguous: <acción>         # confianza 0.5-0.9
  unknown: <acción>           # confianza < 0.5
}
```

### Estrategias disponibles

| Estrategia | Comportamiento |
|---|---|
| `high_confidence` | Ejecuta si confianza >= 0.9 |
| `ambiguous` | Si confianza 0.5-0.9 |
| `unknown` | Si confianza < 0.5 |
| `ask_user(msg, options?)` | Escala al humano con mensaje |
| `use_context(fuente)` | Usa contexto como referencia |
| `infer_from_history` | Infiere desde el audit log |
| `fail_safe()` | Aborta con error |

### Ejemplo con todas las estrategias

```lumen
team = resolve(team_name) {
  high_confidence: use_context(org.teams)
  ambiguous: ask_user("¿Cuál equipo?", options=org.teams.list())
  unknown: fail_safe()
}
```

### Reglas por modo

- **safe:** todo `resolve` debe tener al menos `ambiguous` y `unknown`
- **fast:** el compilador inserta `unknown: fail_safe()` automáticamente si no está presente

---

## 11. Reversibilidad y Undo

### Ventana de undo

```lumen
action pay(supplier, amount):
  reversible: 24h      # se puede deshacer hasta 24 horas después
  audit: full
  execute:
    transfer.money(...)
```

### Ejecutar undo

```lumen
result = undo(action_id="abc-123")

match result:
  ok -> print "Deshecho"
  fail(reason) -> print "No se pudo: ${reason}"
```

### Consultar acciones reversibles

```lumen
recent = audit.query(
  action="transfer.money",
  since=2.hours.ago,
  reversible=true
)

for t in recent:
  print "${t.action_id}: ${t.details.amount}"
```

### Flujo completo de undo interactivo

```lumen
@lumen 1.0
use sensitive.transfer

recent = audit.query(
  action="transfer.money",
  since=2.hours.ago,
  reversible=true
)

print "Transferencias deshacibles:"
for t in recent:
  print "${t.action_id}: ${t.details.amount} a ${t.details.to}"

target_id = listen.user("¿Cuál ID deshacer?")
result = undo(action_id=target_id)

match result:
  ok -> print "Deshecho"
  fail(reason) -> print "No se pudo: ${reason}"
```

---

## 12. Auditoría

### Niveles

```lumen
action x:
  audit: full       # Todo: decisiones, ejecución, resolución
  audit: minimal    # Solo ejecución (default en fast)
  audit: silent     # Nada (solo en fast)
```

### Default por modo

| Modo | Audit default | Puede bajarse |
|---|---|---|
| fast | minimal | Sí (a silent) |
| safe | full | No |
| flow | full | No |

### Acceso al audit log

```lumen
history = audit.query(
  action="transfer.money",
  since=7.days.ago,
  status="completed"
)
```

---

## 13. Manejo de errores

### Errores como valores (Result<T, E>)

```lumen
result = fetch.url("https://api.example.com")

match result:
  ok(response) -> process(response)
  fail(reason) ->
    notify.user("Falló: ${reason}")
    fail_safe()
```

### Propagación con `?`

```lumen
data = fetch.url("https://api.example.com")?
       | parse.json?
       | extract.field("user")?
```

Si cualquier paso devuelve `fail(...)`, el `?` lo propaga hacia arriba sin ejecutar el resto del pipeline.

### `fail_safe()`

Aborta el programa con un error descriptivo:

```lumen
supplier = resolve(name) {
  unknown: fail_safe()  # sin argumento
}

# Con razón explícita
match result:
  fail(stderr) -> fail_safe(reason=stderr)
```

---

## 14. Imports

```lumen
import "./helpers.lumen"        # relativo
import math from std            # stdlib
import comm.email as mail       # alias
```

Reglas:
- Imports relativos usan `"./..."`
- Imports de stdlib usan `from std`
- Aliasing con `as`
- Los imports van antes de las declaraciones

---

## 15. Referencia de errores LMN-XXXX

| Código | Nombre | Descripción |
|---|---|---|
| `LMN-0001` | CapabilityNotDeclared | Capacidad usada sin `use` previo |
| `LMN-0002` | UnresolvedAmbiguity | `resolve` sin estrategia para la confianza obtenida |
| `LMN-0003` | IrreversibleNotDeclared | Operación irreversible sin declaración explícita |
| `LMN-0010` | SyntaxError | Error de parseo general |
| `LMN-0011` | IndentationError | Indentación inconsistente (tabs, espacios incorrectos) |
| `LMN-0020` | ConstantWithoutContext | Constante en modo safe sin `because` |
| `LMN-0030` | TypeMismatch | Error de tipo (incluyendo Money de distinta currency) |
| `LMN-0040` | ModeViolation | Intento de usar modo menos restrictivo que el requerido |
| `LMN-0050` | EscalationTimeout | El humano no respondió en el tiempo configurado |
| `LMN-0060` | UndoOutsideWindow | `undo` intentado fuera de la ventana de reversibilidad |
| `LMN-0070` | UndoChainBroken | Cadena de undo no se pudo completar |
| `LMN-0100` | MissingVersionDeclaration | El programa no empieza con `@lumen <version>` |

---

## Apéndice: gramática EBNF resumida

```ebnf
program        = "@lumen" version, { capability_decl }, { top_level } ;
version        = number, ".", number ;
capability_decl = "use", cap_path, [ "as", identifier ] ;

top_level      = agent_decl | action_decl | function_decl | import_decl | statement ;

action_decl    = "action", identifier, "(", params, ")", ":", action_body ;
action_body    = INDENT, { action_clause }, DEDENT ;
action_clause  = "requires" | "reversible" | "audit" | "escalation" | "execute" ;

function_decl  = "fn", identifier, "(", params, ")", [ "->", type ], ":", block ;

agent_decl     = "agent", identifier, ":", agent_body ;
agent_body     = INDENT, { agent_clause }, DEDENT ;
agent_clause   = "watch" | "schedule" | "state" | "on" | "config" ;

statement      = pipeline | assignment | if_stmt | match_stmt | for_stmt | resolve_block | return_stmt | expr ;
pipeline       = expr, { "|", expr } ;
assignment     = identifier, "=", expr, [ "because", string ] ;

resolve_block  = "resolve", "(", expr, ")", "{", { strategy_clause }, "}" ;
strategy_clause = strategy_name, ":", expr_or_block ;
strategy_name  = "high_confidence" | "ambiguous" | "unknown" | "ask_user"
               | "use_context" | "infer_from_history" | "fail_safe" ;
```
