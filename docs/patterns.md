# Patrones canónicos de Lumen

> 30 patrones de uso común, listos para copiar y adaptar. Cada patrón explica cuándo usarlo y por qué funciona.

---

## Patrón 1: Lectura segura de email

**Cuándo usar:** Cuando necesitas leer emails sin modificarlos.

```lumen
@lumen 1.0
use comm.email

emails = read.email(since="yesterday")
urgent = emails | filter(e -> e.priority > 0.7)
print "Urgentes: ${urgent.length}"
```

**Por qué:** `read.email` es modo fast — no requiere aprobación ni reversibilidad. El filtro es lazy y no ejecuta nada hasta la asignación.

---

## Patrón 2: Envío de email con reversibilidad

**Cuándo usar:** Cuando envías un email que podría necesitarse revocar dentro de la sesión.

```lumen
@lumen 1.0
use comm.email
use comm.send

action send_summary(recipient, content):
  reversible: true
  audit: full
  execute:
    send.email(
      to=recipient,
      subject="Resumen del día",
      body=content
    )

send_summary("equipo@empresa.com", summary_text)
```

**Por qué:** `reversible: true` permite `undo(action_id=...)` sin límite de tiempo. `audit: full` registra todo incluyendo al destinatario.

---

## Patrón 3: Pago con aprobación humana

**Cuándo usar:** Transferencias de dinero que requieren confirmación.

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

**Por qué:** `sensitive.transfer` activa modo safe automáticamente. El `resolve` maneja nombres ambiguos. La ventana de 24h permite correcciones.

---

## Patrón 4: Agent de monitoreo con estado

**Cuándo usar:** Cuando necesitas reaccionar a eventos de forma continua sin procesar duplicados.

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

**Por qué:** El estado `seen_threads` persiste entre eventos. El guard `where` filtra antes de ejecutar el handler. `poll_interval: 5min` evita saturar la API.

---

## Patrón 5: Pipeline con manejo de errores

**Cuándo usar:** Cuando cada paso puede fallar y quieres manejar el error al final.

```lumen
@lumen 1.0
use web.fetch
use data.parse

fn get_user(id) -> Map | Error:
  result = fetch.url("https://api.example.com/users/${id}")?
    | parse.json?
    | extract.field("data")?
  return result

data = get_user(42)

match data:
  ok(user) -> print "Usuario: ${user.name}"
  fail(reason) -> print "Error: ${reason}"
```

**Por qué:** El operador `?` propaga el error sin ejecutar el resto. El `match` obliga a manejar ambos casos.

---

## Patrón 6: Resolución de ambigüedad con opciones

**Cuándo usar:** Cuando el input del usuario puede referirse a varias entidades.

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
      send.email(to=member.email, subject=subject, body=body)

send_to_team("engineering", "Reunión mañana", "10am sala 3")
```

**Por qué:** `options=org.teams.list()` le da al usuario opciones concretas en lugar de un campo libre. `fail_safe()` previene envíos a equipos desconocidos.

---

## Patrón 7: Constantes con contexto obligatorio

**Cuándo usar:** En modo safe, cualquier valor "mágico" necesita justificación.

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
```

**Por qué:** Sin `because`, el compilador rechaza las constantes en modo safe (`LMN-0020`). El contexto aparece en el audit log para trazabilidad legal.

---

## Patrón 8: Undo interactivo de acción previa

**Cuándo usar:** Cuando necesitas revertir una operación específica de las recientes.

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

**Por qué:** `audit.query` filtra por `reversible=true` para no mostrar irreversibles. `listen.user` espera el input. `undo` valida la ventana de tiempo automáticamente.

---

## Patrón 9: Agent con schedule diario

**Cuándo usar:** Tareas recurrentes sin eventos externos (briefings, reportes, recordatorios).

```lumen
@lumen 1.0
use comm.notify
use time.calendar

agent daily_reminder:
  schedule: "0 8 * * *"  # 8am todos los días
  
  on tick:
    events = read.calendar(range="today")
    
    if events.length > 0:
      summary = "Hoy tienes ${events.length} eventos: ${events.titles}"
      notify.user(summary, priority="normal")
  
  config:
    escalation: cli
```

**Por qué:** El cron `"0 8 * * *"` usa formato estándar Unix. `on tick` es el handler del schedule. Sin `watch:` — no hay fuente de eventos externos.

---

## Patrón 10: Aprobación via webhook externo

**Cuándo usar:** Cuando la aprobación la hace un sistema externo (Slack, sistema interno).

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

**Por qué:** `escalation: webhook(...)` envía un POST y espera respuesta. Si no responde en 300s → `LMN-0050 EscalationTimeout`. La ventana de 1h permite correcciones post-aprobación.

---

## Patrón 11: CLI wrapping

**Cuándo usar:** Cuando necesitas ejecutar una herramienta externa (ffmpeg, pandoc, git).

```lumen
@lumen 1.0
use cli.run

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

**Por qué:** `cli.run` captura stdout/stderr. El `match` maneja el error con contexto. `fail_safe(reason=stderr)` escala con información diagnóstica.

---

## Patrón 12: Búsqueda semántica en documentos

**Cuándo usar:** Cuando necesitas encontrar documentos por contenido, no por nombre.

```lumen
@lumen 1.0
use data.search

results = search.semantic(
  query="documentos sobre el proyecto Mars",
  corpus="~/Documents/"
) | sort_by(.relevance, descending) | take(5)

for result in results:
  print "${result.path} (${result.relevance})"
```

**Por qué:** `search.semantic` usa embeddings, no solo keywords. `.relevance` es el score 0.0-1.0. El pipeline `sort_by | take` es idiomático y lazy.

---

## Patrón 13: Extracción de entidades con LLM

**Cuándo usar:** Cuando necesitas extraer datos estructurados de texto libre.

```lumen
@lumen 1.0
use llm.ask
use data.read

text = read.file("./contrato.txt")
entities = llm.extract(text, schema={
  "parties": "List<text>",
  "dates": "List<text>",
  "amounts": "List<text>"
})

print "Partes: ${entities.parties}"
print "Fechas: ${entities.dates}"
```

**Por qué:** `llm.extract` retorna un objeto `Structured` con los campos del schema. Más confiable que `llm.ask` para datos estructurados porque el output es validado.

---

## Patrón 14: Clasificación con LLM

**Cuándo usar:** Cuando necesitas categorizar texto o tomar decisiones basadas en contenido.

```lumen
@lumen 1.0
use llm.ask
use comm.email

emails = read.email(since="yesterday")

for email in emails:
  category = llm.classify(
    input=email.body,
    categories=["urgent", "normal", "spam", "newsletter"]
  )
  
  if category.value == "urgent" and category.confidence > 0.8:
    notify.user("Email urgente: ${email.subject}", priority="high")
```

**Por qué:** `llm.classify` retorna `Confidence<Category>` con `.value` y `.confidence`. El umbral `> 0.8` evita falsos positivos.

---

## Patrón 15: Morning brief completo

**Cuándo usar:** Resumen matutino combinando múltiples fuentes.

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
    emails = read.email(since="last_24h")
    urgent = emails | filter(e -> e.priority > 0.7)
    
    today_events = read.calendar(range="today")
    
    summary = llm.ask(
      prompt="Resume estos correos urgentes y eventos de hoy en 3 bullets",
      context={
        "urgent_emails": urgent,
        "events": today_events
      }
    )
    
    notify.user(summary, priority="high")

morning_brief()
```

**Por qué:** La acción combina cuatro capacidades. El `context` del LLM permite pasar datos estructurados. `reversible: true` permite revocar la notificación.

---

## Patrón 16: Batch processing con for

**Cuándo usar:** Procesar múltiples items del mismo tipo.

```lumen
@lumen 1.0
use data.read
use cli.run

files = ["report1.pdf", "report2.pdf", "report3.pdf"]

for f in files:
  result = cli.run(
    "pdftotext",
    args=[f, f + ".txt"]
  )
  
  match result:
    ok(_) -> print "Convertido: ${f}"
    fail(e) -> print "Error en ${f}: ${e}"
```

**Por qué:** El `for` itera sincrónicamente. Cada iteración es independiente — un error en uno no detiene los demás si se maneja con `match`.

---

## Patrón 17: Condicional con verificación de modo

**Cuándo usar:** Cuando quieres que cierta lógica sea explícitamente safe.

```lumen
@lumen 1.0
use sensitive.transfer

fn check_limit(amount) -> boolean:
  mode: safe
  limit = 50000 because "Límite de operación aprobado por directiva 2026-001"
  return amount <= limit

action pay(amount):
  requires: check_limit(amount)
  reversible: 24h
  audit: full
  execute:
    transfer.money(from=company, to=vendor, amount=amount)
```

**Por qué:** `mode: safe` en la función garantiza que `limit` necesita `because`. La función se usa como precondición en `requires:`.

---

## Patrón 18: Agent con estado acumulativo

**Cuándo usar:** Cuando el agent necesita acumular datos entre eventos.

```lumen
@lumen 1.0
use comm.email

agent email_counter:
  watch: read.email(filter={unread: true})
  
  state:
    daily_count: number = 0
    last_reset: text = ""
  
  on email(e):
    state.daily_count = state.daily_count + 1
    
    if state.daily_count > 50:
      notify.user("Has recibido más de 50 emails hoy", priority="high")
  
  config:
    escalation: cli
    poll_interval: 1min
```

**Por qué:** El estado persiste en `~/.lumen/agents/email_counter/state.json`. Si el agent se reinicia, retoma donde dejó.

---

## Patrón 19: Match con Result<T, E>

**Cuándo usar:** Cualquier operación que puede fallar debe manejarse con match.

```lumen
@lumen 1.0
use web.fetch

fn fetch_config(url) -> Map | Error:
  return fetch.url(url)?
    | parse.json?

config = fetch_config("https://config.example.com/settings.json")

match config:
  ok(data) ->
    print "Version: ${data.version}"
    print "Features: ${data.features.length}"
  fail(reason) ->
    print "No se pudo cargar config: ${reason}"
    fail_safe()
```

**Por qué:** `match` es exhaustivo — el compilador fuerza manejar `ok` y `fail`. No hay excepciones no capturadas en Lumen.

---

## Patrón 20: Tipos Money con operaciones válidas

**Cuándo usar:** Cuando manejas cantidades monetarias y necesitas seguridad de tipos.

```lumen
@lumen 1.0

base = $100 USD
tax = base * 0.16         # OK: Money<USD> * number = Money<USD>
total = base + $50 USD    # OK: Money<USD> + Money<USD> = Money<USD>
discounted = total - $20 USD  # OK

# INCORRECTO — no compila:
# mixed = base + €50 EUR   # LMN-0030: Money<USD> + Money<EUR>
```

**Por qué:** El tipo checker garantiza que no mezcles currencies accidentalmente. Para convertir, usa `convert(amount, to="EUR")` explícitamente.

---

## Patrón 21: Importar módulo externo

**Cuándo usar:** Cuando quieres reutilizar código de otro archivo Lumen.

```lumen
@lumen 1.0

import "./helpers.lumen"
import math from std

result = add_with_tax(100)  # función definida en helpers.lumen
rounded = math.round(result, decimals=2)
```

**En helpers.lumen:**

```lumen
@lumen 1.0

fn add_with_tax(amount):
  tax = amount * 0.16
  return amount + tax
```

**Por qué:** Los imports relativos con `"./"` cargan el archivo desde el directorio del programa. `from std` carga módulos de la stdlib.

---

## Patrón 22: Cadena de undo

**Cuándo usar:** Cuando quieres deshacer múltiples acciones en orden.

```lumen
@lumen 1.0
use sensitive.transfer

recent = audit.query(
  since=1.hours.ago,
  reversible=true
)

# Deshacer todas las transferencias recientes en orden inverso
reversed_list = recent | sort_by(.timestamp, ascending)

for t in reversed_list:
  result = undo(action_id=t.action_id)
  match result:
    ok -> print "Deshecho: ${t.action_id}"
    fail(reason) -> print "Saltando ${t.action_id}: ${reason}"
```

**Por qué:** Ordenar por `ascending` asegura deshacer desde el más reciente. `fail` en un undo no detiene los demás — cada uno se intenta independientemente.

---

## Patrón 23: Dry run antes de ejecutar

**Cuándo usar:** Cuando quieres mostrar lo que se haría antes de hacerlo.

```lumen
@lumen 1.0
use comm.email
use comm.send

fn preview_emails(recipients, subject):
  print "Se enviaría a ${recipients.length} destinatarios:"
  for r in recipients:
    print "  - ${r}"
  print "Asunto: ${subject}"

action bulk_send(recipients, subject, body):
  reversible: true
  audit: full
  execute:
    preview_emails(recipients, subject)
    confirm = listen.user("¿Confirmar envío? (s/n)")
    
    if confirm == "s":
      for r in recipients:
        send.email(to=r, subject=subject, body=body)
    else:
      print "Cancelado"
```

**Por qué:** La función `preview_emails` es fast (solo lectura). El `listen.user` dentro del execute espera confirmación humana explícita.

---

## Patrón 24: Notificación priorizada

**Cuándo usar:** Cuando diferentes eventos tienen diferente urgencia.

```lumen
@lumen 1.0
use comm.notify

fn notify_by_priority(message, priority):
  match priority:
    "critical" ->
      notify.user(message, priority="high")
      speak.text(message)  # también voz
    "high" ->
      notify.user(message, priority="high")
    "normal" ->
      notify.user(message, priority="normal")
    _ ->
      print message  # solo log, sin notificación

notify_by_priority("Servidor caído", "critical")
notify_by_priority("Email urgente", "high")
notify_by_priority("Reunión en 1h", "normal")
```

**Por qué:** El `match` con `_` como wildcard maneja el caso default. `speak.text` complementa la notificación visual para casos críticos.

---

## Patrón 25: Calendario + email juntos

**Cuándo usar:** Correlacionar email con eventos de calendario.

```lumen
@lumen 1.0
use comm.email
use time.calendar
use llm.ask
use comm.notify

action daily_context():
  reversible: true
  audit: full
  execute:
    emails = read.email(since="last_24h")
    events = read.calendar(range="today")
    
    briefing = llm.ask(
      prompt="Dame un briefing de 2 párrafos sobre el día basado en estos datos",
      context={
        "emails": emails | filter(e -> e.priority > 0.5),
        "events": events
      }
    )
    
    notify.user(briefing, priority="normal")

daily_context()
```

**Por qué:** Pasar ambas fuentes al LLM como contexto permite correlaciones que ninguna fuente individual puede ver (ej. "el email de Pedro es sobre la reunión de las 3pm").

---

## Patrón 26: Deploy con aprobación

**Cuándo usar:** Deployments a producción que requieren autorización.

```lumen
@lumen 1.0
use sensitive.transfer

action deploy_service(service_name, version):
  requires: version != ""
  reversible: 1h
  audit: full
  escalation: webhook(
    url="https://deploys.company.com/approve",
    timeout=600s
  )
  execute:
    deploy.production(
      system=service_name,
      version=version
    ) because "Deploy programado sprint ${version}"

deploy_service("api-gateway", "v2.3.1")
```

**Por qué:** El webhook notifica al equipo de ops que debe aprobar. La ventana de 1h permite rollback rápido. El `because` documenta el contexto en el audit log.

---

## Patrón 27: Borrado seguro con ventana de undo

**Cuándo usar:** Cuando necesitas borrar archivos pero quieres poder recuperarlos.

```lumen
@lumen 1.0
use data.read

action safe_delete(path):
  requires: path != ""
  reversible: 7d
  audit: full
  execute:
    # Primero hacer backup
    content = read.file(path)
    backup_path = path + ".backup." + now().timestamp
    write.file(backup_path, content)
    
    # Luego borrar
    delete.permanent(path) because "Borrado solicitado por usuario"

safe_delete("./reports/old_data.csv")
```

**Por qué:** El backup previo extiende la ventana de recuperación más allá de lo que el runtime garantiza. `7d` de ventana formal + backup manual = doble protección.

---

## Patrón 28: Webhook server simple

**Cuándo usar:** Cuando Lumen necesita recibir eventos de sistemas externos.

```lumen
@lumen 1.0
use web.fetch

agent webhook_receiver:
  watch: serve.webhook(port=8080, handler=on_request)
  
  on request(req) where req.path == "/lumen/approve":
    action_id = req.body.action_id
    approved = req.body.approved
    
    if approved:
      print "Aprobado: ${action_id}"
    else:
      print "Rechazado: ${action_id}"
  
  config:
    escalation: cli
```

**Por qué:** `serve.webhook` abre un servidor HTTP. El handler `on_request` procesa cada request. El guard `where req.path == "..."` filtra rutas.

---

## Patrón 29: Pipe de CLI commands

**Cuándo usar:** Cuando necesitas encadenar varios comandos de shell.

```lumen
@lumen 1.0
use cli.run

action process_logs(log_path, output_path):
  reversible: false
  audit: full
  execute:
    result = cli.pipe([
      ["grep", "ERROR", log_path],
      ["sort"],
      ["uniq", "-c"],
      ["sort", "-rn"]
    ])
    
    match result:
      ok(output) ->
        write.file(output_path, output.stdout)
        print "Procesado: ${output_path}"
      fail(stderr) -> fail_safe(reason=stderr)

process_logs("./app.log", "./error_summary.txt")
```

**Por qué:** `cli.pipe` encadena comandos en un pipeline de shell real. Más eficiente que ejecutar cada uno por separado y pasar el output manualmente.

---

## Patrón 30: Agent con múltiples fuentes (watches)

**Cuándo usar:** Cuando un agent necesita monitorear múltiples canales.

```lumen
@lumen 1.0
use comm.email
use comm.notify

agent multi_monitor:
  watch: read.email(filter={unread: true})
  
  state:
    email_count: number = 0
    alert_threshold: number = 0
  
  on email(e) where e.priority > 0.8:
    state.email_count = state.email_count + 1
    summary = summarize.email(e, max_lines=2)
    notify.user("URGENTE (${state.email_count} hoy): ${summary}", priority="high")
  
  on email(e) where e.from == "ceo@empresa.com":
    notify.user("Email del CEO: ${e.subject}", priority="high")
  
  on email(e):
    pass  # los demás se ignoran
  
  config:
    escalation: cli
    poll_interval: 2min
```

**Por qué:** Múltiples cláusulas `on` se evalúan en orden. El primer match que ejecuta algo "consume" el evento (no ejecuta los siguientes). El `on email(e)` sin guard es el catch-all.

---

## Notas de uso

### Orden de cláusulas en actions

El orden correcto es:
1. `requires:`
2. `reversible:`
3. `audit:`
4. `escalation:` (opcional)
5. `execute:`

Cambiar el orden produce `LMN-0010 SyntaxError`.

### Cuándo usar fn vs action

- **fn:** lógica pura, sin efectos secundarios externos, sin necesidad de aprobación
- **action:** operaciones con efectos (enviar, transferir, borrar, modificar)

### Cuándo usar agent vs script

- **script:** tarea de una sola vez (lee, procesa, imprime, termina)
- **agent:** proceso continuo que reacciona a eventos o schedule

### Pipeline vs for

Para colecciones, prefiere pipeline sobre for cuando la transformación es funcional:

```lumen
# Preferido
urgent = emails | filter(e -> e.priority > 0.7) | take(10)

# Solo cuando necesitas side effects por item
for email in urgent:
  send.notification(email.id)
```
