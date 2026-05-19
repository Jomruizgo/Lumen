# EXAMPLES.md — Programas canónicos

> Estos programas son **casos de prueba de aceptación**. Si el compilador y runtime no los manejan correctamente, el lenguaje no está terminado.

Cada ejemplo tiene:
- **Programa Lumen** (lo que se escribe)
- **Comportamiento esperado** (qué debe pasar al ejecutar)
- **Audit log esperado** (resumen de las entradas que debe generar)
- **Errores esperados si se modifica de cierta forma** (tests negativos)

---

## Ejemplo 1: Hello World (modo fast)

### Programa: `examples/01_hello.lumen`

```lumen
@lumen 1.0

print "Hello, World"
```

### Comportamiento esperado
- Imprime `Hello, World` a stdout
- Modo detectado: `fast`
- Audit log: una entrada `execution`

### Test negativo
Si quitas `@lumen 1.0` → error `LMN-0100 MissingVersionDeclaration`

---

## Ejemplo 2: Función simple con tipos inferidos

### Programa: `examples/02_function.lumen`

```lumen
@lumen 1.0

fn add(a, b):
  return a + b

result = add(2, 3)
print "Result: ${result}"
```

### Comportamiento esperado
- Imprime `Result: 5`
- Tipos inferidos: `a: number`, `b: number`, return `number`
- Modo: `fast`

---

## Ejemplo 3: Lectura de email con resolución

### Programa: `examples/03_email_read.lumen`

```lumen
@lumen 1.0
use comm.email

emails = read.email(since="yesterday")
urgent = emails | filter(e -> e.priority > 0.7)

print "Tienes ${urgent.length} correos urgentes"
```

### Comportamiento esperado
- Llama al provider de email (mocked en tests)
- Filtra por priority
- Modo: `fast` (solo lectura)
- Audit log: entrada por cada llamada a capability

### Test negativo
Si quitas `use comm.email` pero usas `read.email` → error `LMN-0001 CapabilityNotDeclared`

---

## Ejemplo 4: Pago con aprobación humana (modo safe)

### Programa: `examples/04_payment.lumen`

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

### Comportamiento esperado
- Modo: `safe` (por `transfer.money`)
- Antes de ejecutar: pide aprobación humana (CLI o webhook)
- Si aprobado: ejecuta y registra compensating action para undo
- Audit log: completo, incluyendo decisión, resolución, aprobación, ejecución

### Test negativo 1
Si quitas `reversible: 24h` → error `LMN-0003 IrreversibleNotDeclared`

### Test negativo 2
Si declaras `mode: fast` → error `LMN-0040 ModeViolation`

---

## Ejemplo 5: Agente de monitoreo (modo flow)

### Programa: `examples/05_inbox_agent.lumen`

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

### Comportamiento esperado
- Modo: `flow`
- Se ejecuta como subprocess persistente (`lumen agent start inbox_monitor`)
- Cada 5 minutos chequea correos
- Por cada correo urgente nuevo, notifica al usuario
- Estado persistido en `~/.lumen/agents/inbox_monitor/state.json`
- Audit log completo

---

## Ejemplo 6: Pipeline con manejo de errores

### Programa: `examples/06_pipeline_errors.lumen`

```lumen
@lumen 1.0
use web.fetch
use data.parse

fn get_user_data(user_id) -> Map | Error:
  result = fetch.url("https://api.example.com/users/${user_id}")?
    | parse.json?
    | extract.field("data")?
  
  return result

data = get_user_data(42)

match data:
  ok(user) -> print "Usuario: ${user.name}"
  fail(reason) -> print "Error: ${reason}"
```

### Comportamiento esperado
- Pipeline corre lazy
- Si fetch falla, el `?` propaga error sin ejecutar pasos siguientes
- `match` maneja ambos casos
- Modo: `fast`

---

## Ejemplo 7: Resolución con múltiples estrategias

### Programa: `examples/07_resolution.lumen`

```lumen
@lumen 1.0
use comm.email
use comm.send

action send_to_team(team_name, subject, body):
  reversible: false
  audit: full
  execute:
    team = resolve(team_name) {
      high_confidence: use_context(org.teams)
      ambiguous: ask_user("¿Cuál equipo?", options=org.teams.list())
      unknown: fail_safe()
    }
    
    for member in team.members:
      send.email(to=member.email, subject, body)

send_to_team("engineering", "Reunión mañana", "10am sala 3")
```

### Comportamiento esperado
- Modo: `safe` (por `reversible: false`)
- Si `engineering` resuelve con alta confianza → ejecuta directo
- Si es ambiguo → pregunta al usuario
- Si no se conoce → falla seguro
- Cada email enviado se loggea individualmente

---

## Ejemplo 8: Uso de CLI wrapping

### Programa: `examples/08_cli_wrap.lumen`

```lumen
@lumen 1.0
use cli.run
use data.parse

# Wrap de ffmpeg para conversión
action convert_video(input_path, output_path):
  reversible: false
  audit: full
  execute:
    result = cli.run(
      "ffmpeg",
      args=["-i", input_path, "-c:v", "libx264", output_path]
    )
    
    match result:
      ok(output) -> return output_path
      fail(stderr) -> fail_safe(reason=stderr)

convert_video("./input.mp4", "./output.mp4")
```

### Comportamiento esperado
- Modo: `safe`
- Ejecuta ffmpeg en subprocess
- Captura stdout/stderr
- Si falla, escala con razón clara

---

## Ejemplo 9: Búsqueda semántica

### Programa: `examples/09_semantic_search.lumen`

```lumen
@lumen 1.0
use data.search
use data.read

results = search.semantic(
  query="documentos sobre el proyecto Mars",
  corpus="~/Documents/"
) | sort_by(.relevance, descending) | take(5)

for result in results:
  print "${result.path} (${result.relevance})"
```

### Comportamiento esperado
- Modo: `fast`
- Indexa el corpus (con cache)
- Devuelve resultados por relevancia semántica
- No solo por nombre de archivo

---

## Ejemplo 10: Webhook escalation

### Programa: `examples/10_webhook_approval.lumen`

```lumen
@lumen 1.0
use sensitive.transfer

action critical_transfer(amount):
  requires: amount > 10000
  reversible: 1h
  audit: full
  escalation: webhook(
    url="https://approvals.company.com/lumen",
    timeout=300s
  )
  execute:
    transfer.money(
      from=treasury,
      to=operations,
      amount
    ) because "Movimiento mensual de tesorería"

critical_transfer($50000 USD)
```

### Comportamiento esperado
- Modo: `safe`
- Envía POST al webhook con detalles
- Espera respuesta hasta 5 minutos
- Si timeout → error `LMN-0050 EscalationTimeout`
- Si rechazado → no ejecuta, loggea
- Si aprobado → ejecuta y prepara undo de 1h

---

## Ejemplo 11: Undo de acción previa

### Programa: `examples/11_undo.lumen`

```lumen
@lumen 1.0
use sensitive.transfer

# Listar transferencias recientes
recent = audit.query(
  action="transfer.money",
  since=2.hours.ago,
  reversible=true
)

print "Transferencias deshacibles:"
for t in recent:
  print "${t.action_id}: ${t.details.amount} a ${t.details.to}"

# Deshacer una específica (usuario provee el id)
target_id = listen.user("¿Cuál ID deshacer?")
result = undo(action_id=target_id)

match result:
  ok -> print "Deshecho"
  fail(reason) -> print "No se pudo: ${reason}"
```

### Comportamiento esperado
- Lista transferencias recientes desde audit log
- Pregunta al usuario cuál deshacer
- Ejecuta compensating action si está dentro de ventana
- Modo: `safe`

---

## Ejemplo 12: Programa completo "Morning brief"

### Programa: `examples/12_morning_brief.lumen`

```lumen
@lumen 1.0
use comm.email
use comm.notify
use time.calendar
use llm.ask

action morning_brief():
  reversible: true
  audit: full
  execute:
    # Email
    emails = read.email(since="last_24h")
    urgent = emails | filter(e -> e.priority > 0.7)
    
    # Calendar
    today_events = read.calendar(range="today")
    
    # Sintetizar
    summary = llm.ask(
      prompt="Resume estos correos urgentes y eventos de hoy",
      context={
        "urgent_emails": urgent,
        "events": today_events
      }
    )
    
    # Entregar
    notify.user(summary, priority="high")

# Ejecutar
morning_brief()
```

### Comportamiento esperado
- Modo: `safe` (por audit: full + llm.ask)
- Lee correos y calendario
- Sintetiza con LLM
- Notifica al usuario
- Reversible (la notificación se puede revocar dentro de la sesión)

---

## Ejemplo 13: Manejo de Money con currencies

### Programa: `examples/13_money.lumen`

```lumen
@lumen 1.0

usd_amount = $100 USD
eur_amount = €50 EUR

# Esto compila
total_usd = usd_amount + $50 USD       # 150 USD

# Esto NO compila: error LMN-0030 TypeMismatch
total_mixed = usd_amount + eur_amount  # ❌
```

### Comportamiento esperado
- Suma con misma currency funciona
- Suma con distintas falla en compilación
- Mensaje: "Cannot add Money<USD> and Money<EUR>. Use convert() explicitly."

---

## Ejemplo 14: Constantes con `because`

### Programa: `examples/14_constants.lumen`

```lumen
@lumen 1.0
use sensitive.transfer

action calculate_tax(amount):
  reversible: true
  audit: full
  execute:
    tax_rate = 0.16 because "IVA México 2026, ley vigente"
    deadline = 2026-12-31 because "Cierre fiscal anual"
    
    tax = amount * tax_rate
    return tax

calculate_tax($1000 USD)
```

### Test negativo
Si quitas `because "..."` en modo safe → error `LMN-0020 ConstantWithoutContext`

---

## Ejemplo 15: Agent con schedule

### Programa: `examples/15_scheduled_agent.lumen`

```lumen
@lumen 1.0
use comm.notify
use time.calendar

agent daily_reminder:
  schedule: "0 8 * * *"  # 8am todos los días (cron syntax)
  
  on tick:
    events = read.calendar(range="today")
    
    if events.length > 0:
      summary = "Hoy tienes ${events.length} eventos: ${events.titles}"
      notify.user(summary, priority="normal")
  
  config:
    escalation: cli
```

### Comportamiento esperado
- Modo: `flow`
- Se ejecuta a las 8am cada día (mientras el agent esté corriendo)
- Si hay eventos, notifica

---

## Programas de benchmark

Estos sirven para los benchmarks de tokens y corrección:

### Lista canónica de tareas

Cada una se implementa en Python equivalente para comparar:

1. **Leer N correos y contar urgentes** — Test de eficiencia básica
2. **Procesar un PDF y extraer fechas** — Test de pipeline
3. **Monitorear carpeta y mover archivos por tipo** — Test de agent simple
4. **Hacer 3 transferencias con aprobación** — Test de modo safe
5. **Sintetizar resumen diario** — Test de integración LLM
6. **Convertir 100 imágenes** — Test de CLI wrap + paralelismo
7. **Buscar en docs y resumir hallazgos** — Test de search + LLM
8. **Crear evento de calendario desde texto natural** — Test de resolución
9. **Notificar cuando llegue email específico** — Test de agent con watch
10. **Deshacer última transacción** — Test de undo

Para cada uno se mide:
- Tokens necesarios para que un LLM genere la solución en Python
- Tokens necesarios para Lumen
- Tasa de éxito al primer intento
- Líneas de código

**Target:** Lumen usa ≤50% tokens y tiene ≥20% más éxito al primer intento.

---

## Criterios de aceptación globales

Todos los ejemplos de 1 a 15 deben:

1. **Parsear correctamente** (Track A)
2. **Pasar type checking** (Track A)
3. **Detectar modo correctamente** (Track A)
4. **Ejecutarse en runtime con mocks** (Track B)
5. **Generar audit log correcto** (Track B)
6. **Tests negativos fallan con error correcto** (Track A + B)

Cuando estos 6 puntos están verdes para todos los ejemplos, el core del lenguaje está completo.
