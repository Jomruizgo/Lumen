# Errores comunes en Lumen

> 20 errores frecuentes con código incorrecto, código correcto y explicación.

---

## 1. Usar capacidad sin declararla

**Error:** `LMN-0001 CapabilityNotDeclared`

**Código incorrecto:**
```lumen
@lumen 1.0

emails = read.email(since="yesterday")  # CapabilityNotDeclared
```

**Código correcto:**
```lumen
@lumen 1.0
use comm.email

emails = read.email(since="yesterday")
```

**Por qué falla:** Toda capacidad debe declararse con `use` antes de usarse. El compilador no infiere qué capacidades usa el programa — son declaraciones explícitas de permisos.

---

## 2. Omitir la declaración de versión

**Error:** `LMN-0100 MissingVersionDeclaration`

**Código incorrecto:**
```lumen
use comm.email

emails = read.email(since="yesterday")
```

**Código correcto:**
```lumen
@lumen 1.0
use comm.email

emails = read.email(since="yesterday")
```

**Por qué falla:** `@lumen 1.0` debe ser la primera línea de todo programa. No es opcional.

---

## 3. Usar tabs en lugar de 2 espacios

**Error:** `LMN-0011 IndentationError`

**Código incorrecto:**
```lumen
@lumen 1.0

fn add(a, b):
	return a + b  # tab aquí
```

**Código correcto:**
```lumen
@lumen 1.0

fn add(a, b):
  return a + b  # 2 espacios
```

**Por qué falla:** Lumen usa exclusivamente 2 espacios para indentación. Los tabs producen error léxico inmediato.

---

## 4. Omitir `reversible:` en modo safe

**Error:** `LMN-0003 IrreversibleNotDeclared`

**Código incorrecto:**
```lumen
@lumen 1.0
use sensitive.transfer

action pay(amount):
  audit: full
  execute:
    transfer.money(from=a, to=b, amount=amount)
```

**Código correcto:**
```lumen
@lumen 1.0
use sensitive.transfer

action pay(amount):
  reversible: 24h   # o reversible: false si es intencional
  audit: full
  execute:
    transfer.money(from=a, to=b, amount=amount)
```

**Por qué falla:** En modo safe, el compilador exige que declares explícitamente si la acción es reversible o no. La omisión es ambigua y se rechaza.

---

## 5. Sumar monedas distintas

**Error:** `LMN-0030 TypeMismatch`

**Código incorrecto:**
```lumen
@lumen 1.0

usd = $100 USD
eur = €50 EUR
total = usd + eur  # TypeMismatch: Money<USD> + Money<EUR>
```

**Código correcto:**
```lumen
@lumen 1.0

usd = $100 USD
extra = $50 USD
total = usd + extra  # Money<USD> + Money<USD> = OK

# Para mezclar currencies, usar convert() explícitamente:
# total = usd + convert(eur, to="USD")
```

**Por qué falla:** `Money<USD>` y `Money<EUR>` son tipos distintos. El compilador no hace conversión implícita para evitar errores de cambio de divisas.

---

## 6. Constante mágica sin `because` en modo safe

**Error:** `LMN-0020 ConstantWithoutContext`

**Código incorrecto:**
```lumen
@lumen 1.0
use sensitive.transfer

action calculate_tax(amount):
  reversible: true
  audit: full
  execute:
    rate = 0.16  # ConstantWithoutContext en modo safe
    return amount * rate
```

**Código correcto:**
```lumen
@lumen 1.0
use sensitive.transfer

action calculate_tax(amount):
  reversible: true
  audit: full
  execute:
    rate = 0.16 because "IVA México 2026, ley vigente"
    return amount * rate
```

**Por qué falla:** En modo safe, valores numéricos o strings literales sin contexto no están permitidos. El `because` documenta la razón del valor y aparece en el audit log.

---

## 7. Declarar `mode: fast` cuando se usa `sensitive.*`

**Error:** `LMN-0040 ModeViolation`

**Código incorrecto:**
```lumen
@lumen 1.0
use sensitive.transfer

action pay(amount):
  mode: fast   # ModeViolation
  reversible: 24h
  audit: full
  execute:
    transfer.money(from=a, to=b, amount=amount)
```

**Código correcto:**
```lumen
@lumen 1.0
use sensitive.transfer

action pay(amount):
  reversible: 24h
  audit: full
  execute:
    transfer.money(from=a, to=b, amount=amount)
# El modo safe se infiere automáticamente de sensitive.transfer
```

**Por qué falla:** Los modos solo se pueden forzar hacia niveles más restrictivos. `sensitive.*` requiere al menos modo safe; no puedes forzarlo a fast.

---

## 8. Agent sin `watch:` ni `schedule:`

**Error:** `LMN-0010 SyntaxError`

**Código incorrecto:**
```lumen
@lumen 1.0

agent monitor:
  on email(e):
    pass
```

**Código correcto:**
```lumen
@lumen 1.0
use comm.email

agent monitor:
  watch: read.email(filter={unread: true})
  
  on email(e):
    pass
  
  config:
    escalation: cli
```

**Por qué falla:** Un agent debe tener una fuente de eventos: `watch:` (stream reactivo) o `schedule:` (cron). Sin ninguna, no sabe cuándo ejecutar sus handlers.

---

## 9. `resolve` sin estrategia completa en modo safe

**Error:** `LMN-0002 UnresolvedAmbiguity`

**Código incorrecto:**
```lumen
@lumen 1.0
use sensitive.transfer

action pay(name, amount):
  reversible: 24h
  audit: full
  execute:
    supplier = resolve(name) {
      high_confidence: use_context(crm.suppliers)
      # Faltan ambiguous y unknown
    }
    transfer.money(from=a, to=supplier, amount=amount)
```

**Código correcto:**
```lumen
@lumen 1.0
use sensitive.transfer

action pay(name, amount):
  reversible: 24h
  audit: full
  execute:
    supplier = resolve(name) {
      high_confidence: use_context(crm.suppliers)
      ambiguous: ask_user("¿Cuál proveedor?")
      unknown: fail_safe()
    }
    transfer.money(from=a, to=supplier, amount=amount)
```

**Por qué falla:** En modo safe, el bloque `resolve` debe manejar todos los casos de confianza. Si el LLM resolver retorna confianza media y no hay estrategia `ambiguous`, el programa no sabe qué hacer.

---

## 10. Usar indentación de 4 espacios

**Error:** `LMN-0011 IndentationError`

**Código incorrecto:**
```lumen
@lumen 1.0

fn calculate(x):
    result = x * 2    # 4 espacios — incorrecto
    return result
```

**Código correcto:**
```lumen
@lumen 1.0

fn calculate(x):
  result = x * 2    # 2 espacios — correcto
  return result
```

**Por qué falla:** Lumen es estricto: exactamente 2 espacios por nivel. 3, 4 o cualquier otro número produce `IndentationError`.

---

## 11. Llamar a función sin paréntesis

**Error:** `LMN-0010 SyntaxError`

**Código incorrecto:**
```lumen
@lumen 1.0

result = add 2, 3   # SyntaxError
```

**Código correcto:**
```lumen
@lumen 1.0

result = add(2, 3)  # paréntesis obligatorios
```

**Por qué falla:** Lumen no tiene "call sin paréntesis" como Ruby o Haskell. Todas las llamadas requieren `nombre(args)`.

---

## 12. Olvidar `execute:` en una action

**Error:** `LMN-0010 SyntaxError`

**Código incorrecto:**
```lumen
@lumen 1.0

action do_work(x):
  requires: x > 0
  reversible: true
  audit: full
  result = x * 2   # esto va en execute:, no aquí
```

**Código correcto:**
```lumen
@lumen 1.0

action do_work(x):
  requires: x > 0
  reversible: true
  audit: full
  execute:
    result = x * 2
    return result
```

**Por qué falla:** El cuerpo de la action va dentro de `execute:`. Las líneas fuera de las cláusulas reconocidas son error de sintaxis.

---

## 13. `return` fuera de función o action

**Error:** `LMN-0010 SyntaxError`

**Código incorrecto:**
```lumen
@lumen 1.0

x = 5
return x  # SyntaxError: return fuera de función
```

**Código correcto:**
```lumen
@lumen 1.0

fn get_x():
  return 5

x = get_x()
```

**Por qué falla:** `return` solo es válido dentro de `fn` o dentro del bloque `execute:` de una `action`.

---

## 14. Agent con `watch:` y `schedule:` juntos

**Error:** `LMN-0010 SyntaxError`

**Código incorrecto:**
```lumen
@lumen 1.0
use comm.email

agent both:
  watch: read.email(filter={unread: true})
  schedule: "0 8 * * *"  # no pueden coexistir
  
  on email(e):
    pass
```

**Código correcto:**
```lumen
# Opción A: solo watch
agent email_monitor:
  watch: read.email(filter={unread: true})
  on email(e): pass
  config: escalation: cli

# Opción B: solo schedule
agent daily_reminder:
  schedule: "0 8 * * *"
  on tick: notify.user("Buenos días", priority="normal")
  config: escalation: cli
```

**Por qué falla:** `watch:` y `schedule:` son mutuamente excluyentes. Son dos modos de disparo diferentes (reactivo vs. programado).

---

## 15. No manejar el resultado de una operación fallible

**Antipatrón:** Ignorar errores silenciosamente.

**Código problemático:**
```lumen
@lumen 1.0
use web.fetch

data = fetch.url("https://api.example.com/data")
print "Datos: ${data.items}"  # si fetch falló, data es Error
```

**Código correcto:**
```lumen
@lumen 1.0
use web.fetch

data = fetch.url("https://api.example.com/data")

match data:
  ok(response) -> print "Datos: ${response.items}"
  fail(reason) -> print "Error al cargar: ${reason}"
```

**Por qué falla:** `fetch.url` retorna `Response | Error`. Acceder a `.items` en un `Error` es `LMN-0030 TypeMismatch` en tiempo de compilación. Siempre usa `match` o `?` para manejar errores.

---

## 16. Usar string sin interpolación cuando necesitas un valor

**Antipatrón:** Olvidar `${...}`.

**Código problemático:**
```lumen
@lumen 1.0

name = "Lumen"
msg = "Hello name"  # "name" es texto literal, no la variable
```

**Código correcto:**
```lumen
@lumen 1.0

name = "Lumen"
msg = "Hello ${name}"  # interpolación con ${...}
```

**Por qué falla:** Sin `${...}`, `name` dentro de un string es literalmente el texto "name", no el valor de la variable.

---

## 17. Usar `because` en modo fast para string no mágico

**Antipatrón:** Usar `because` innecesariamente.

**Código problemático:**
```lumen
@lumen 1.0

greeting = "Hello" because "saludamos al usuario"  # innecesario en fast
```

**Código correcto:**
```lumen
@lumen 1.0

greeting = "Hello"  # en fast, because es opcional
```

**Cuándo se necesita:** `because` es obligatorio solo en modo safe para constantes numéricas o strings que codifican valores de negocio. En modo fast es siempre opcional.

---

## 18. Acceder a campo de variable no tipada

**Error:** `LMN-0030 TypeMismatch`

**Código problemático:**
```lumen
@lumen 1.0

x = 42
print x.name  # number no tiene campo .name
```

**Código correcto:**
```lumen
@lumen 1.0
use comm.email

emails = read.email(since="yesterday")
first = emails[0]
print first.subject  # Email sí tiene .subject
```

**Por qué falla:** El type checker valida accesos a campos. Un `number` no tiene `.name`. Si el tipo es `any`, el acceso se permite pero puede fallar en runtime.

---

## 19. Pasar Money a función que espera number

**Error:** `LMN-0030 TypeMismatch`

**Código problemático:**
```lumen
@lumen 1.0

fn double(n: number) -> number:
  return n * 2

amount = $100 USD
result = double(amount)  # TypeMismatch: Money<USD> vs number
```

**Código correcto:**
```lumen
@lumen 1.0

fn double(n: number) -> number:
  return n * 2

amount = 100
result = double(amount)  # number, OK

# O si necesitas operar sobre el monto de Money:
money_amount = $100 USD
doubled_money = money_amount * 2  # Money<USD> * number = Money<USD>
```

**Por qué falla:** `Money<USD>` y `number` son tipos distintos. El compilador no extrae el número de un Money implícitamente para evitar pérdidas de información de currency.

---

## 20. `undo` fuera de la ventana de reversibilidad

**Error:** `LMN-0060 UndoOutsideWindow`

**Situación:**
```lumen
@lumen 1.0
use sensitive.transfer

# Si pay_supplier tiene reversible: 1h y ya pasaron 2 horas:
result = undo(action_id="action-abc-123")

match result:
  ok -> print "Deshecho"
  fail(reason) -> print "No se pudo: ${reason}"
  # reason = "UndoOutsideWindow: action-abc-123 expired 1h ago"
```

**Cómo evitarlo:**
```lumen
# Siempre verificar la ventana antes de intentar undo
recent = audit.query(
  action="transfer.money",
  since=1.hours.ago,   # limitar al tiempo de la ventana
  reversible=true
)

if recent.length == 0:
  print "No hay transferencias deshacibles en la última hora"
else:
  # ... mostrar opciones y pedir ID
```

**Por qué falla:** `undo` verifica que la acción esté dentro de su ventana de reversibilidad. Si `reversible: 1h` y ya pasaron 90 minutos, el undo es imposible.

---

## Resumen rápido de errores

| Error | Código | Causa más común |
|---|---|---|
| CapabilityNotDeclared | LMN-0001 | Falta `use <capability>` |
| UnresolvedAmbiguity | LMN-0002 | `resolve` sin estrategia para la confianza obtenida |
| IrreversibleNotDeclared | LMN-0003 | Falta `reversible:` en modo safe |
| SyntaxError | LMN-0010 | Sintaxis incorrecta (paréntesis, colon, estructura) |
| IndentationError | LMN-0011 | Tabs o número incorrecto de espacios |
| ConstantWithoutContext | LMN-0020 | Falta `because` en modo safe |
| TypeMismatch | LMN-0030 | Tipos incompatibles, Money de distinta currency |
| ModeViolation | LMN-0040 | `mode: fast` con capabilities que requieren safe |
| EscalationTimeout | LMN-0050 | Webhook no respondió en tiempo |
| UndoOutsideWindow | LMN-0060 | `undo` después de la ventana de reversibilidad |
| UndoChainBroken | LMN-0070 | Cadena de undo parcialmente fallida |
| MissingVersionDeclaration | LMN-0100 | No empieza con `@lumen 1.0` |
