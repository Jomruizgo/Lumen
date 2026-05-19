# Catálogo de errores Lumen (LMN-XXXX)

> Referencia completa de todos los códigos de error del compilador y runtime de Lumen.

---

## LMN-0000 — InternalError

**Descripción:** Error interno del compilador sin clasificar. Indica un fallo inesperado en el pipeline de compilación.

**Ejemplo:**
```lumen
# Código que produce un estado interno inconsistente
```

**Cómo arreglarlo:** Reportar el bug incluyendo el source completo del programa.

---

## LMN-0099 — RuntimeError

**Descripción:** Error en tiempo de ejecución sin clasificar. Ocurre cuando el intérprete encuentra una condición inesperada no cubierta por otros códigos.

**Ejemplo:**
```lumen
# Operación que falla en runtime sin categoría específica
```

**Cómo arreglarlo:** Verificar que las capacidades usadas están disponibles y configuradas correctamente.

---

## LMN-0001 — CapabilityNotDeclared

**Descripción:** Se usó una capacidad que no fue declarada con `use` al inicio del programa.

**Ejemplo que lo dispara:**
```lumen
@lumen 1.0

# Falta: use comm.email
emails = read.email(since="yesterday")
```

**Cómo arreglarlo:**
Agrega la declaración `use` correspondiente al inicio del programa:
```lumen
@lumen 1.0
use comm.email

emails = read.email(since="yesterday")
```

---

## LMN-0002 — UnresolvedAmbiguity

**Descripción:** Un bloque `resolve(...)` no tiene estrategia para el nivel de confianza obtenido, o en modo safe le falta `ambiguous:` o `unknown:`.

**Ejemplo que lo dispara:**
```lumen
@lumen 1.0
use sensitive.transfer

action pay(supplier):
  reversible: 24h
  execute:
    # En modo safe, falta ambiguous: y unknown:
    entity = resolve(supplier) {
      high_confidence: use_context(crm)
    }
```

**Cómo arreglarlo:**
```lumen
entity = resolve(supplier) {
  high_confidence: use_context(crm)
  ambiguous: ask_user("¿Cuál proveedor?")
  unknown: fail_safe()
}
```

---

## LMN-0003 — IrreversibleNotDeclared

**Descripción:** Una action usa capacidades irreversibles (como `transfer.money`, `delete.permanent`) pero no declara `reversible:` explícitamente.

**Ejemplo que lo dispara:**
```lumen
@lumen 1.0
use sensitive.transfer

action pay(supplier, amount):
  # Falta: reversible: 24h
  execute:
    transfer.money(from=company, to=supplier, amount=amount)
```

**Cómo arreglarlo:**
```lumen
action pay(supplier, amount):
  reversible: 24h
  execute:
    transfer.money(from=company, to=supplier, amount=amount)
```

Si la operación es genuinamente irreversible:
```lumen
action pay(supplier, amount):
  reversible: false
  execute:
    transfer.money(from=company, to=supplier, amount=amount)
```

---

## LMN-0010 — SyntaxError

**Descripción:** Error de parseo. La sintaxis del programa no es válida.

**Ejemplo que lo dispara:**
```lumen
@lumen 1.0

fn add a b   # Falta paréntesis y dos puntos
  return a + b
```

**Cómo arreglarlo:** Corrige la sintaxis según la especificación:
```lumen
fn add(a, b):
  return a + b
```

---

## LMN-0011 — IndentationError

**Descripción:** Indentación incorrecta. Lumen usa exactamente 2 espacios, no tabs ni otros números de espacios.

**Ejemplo que lo dispara:**
```lumen
@lumen 1.0

fn greet(name):
    print "Hello ${name}"  # 4 espacios — inválido
```

**Cómo arreglarlo:**
```lumen
fn greet(name):
  print "Hello ${name}"  # 2 espacios — correcto
```

---

## LMN-0020 — ConstantWithoutContext

**Descripción:** En modo `safe`, las constantes numéricas o strings deben tener anotación `because "..."` que explique su origen.

**Ejemplo que lo dispara:**
```lumen
@lumen 1.0
use sensitive.transfer

action calculate_tax(amount):
  reversible: true
  audit: full
  execute:
    tax_rate = 0.16  # En modo safe: LMN-0020
    return amount * tax_rate
```

**Cómo arreglarlo:**
```lumen
tax_rate = 0.16 because "IVA México 2026, ley vigente"
```

---

## LMN-0030 — TypeMismatch

**Descripción:** Error de tipos. Ejemplo clásico: sumar `Money<USD>` con `Money<EUR>`.

**Ejemplo que lo dispara:**
```lumen
@lumen 1.0

usd = $100 USD
eur = €50 EUR
total = usd + eur  # LMN-0030: Cannot add Money<USD> and Money<EUR>
```

**Cómo arreglarlo:**
Convierte explícitamente antes de sumar:
```lumen
eur_to_usd = convert(eur, to="USD")
total = usd + eur_to_usd
```
O trabaja con la misma moneda:
```lumen
total_usd = $100 USD + $50 USD  # OK: 150 USD
```

---

## LMN-0040 — ModeViolation

**Descripción:** El programa declara `mode: fast` explícitamente pero usa capacidades que requieren modo `safe` (como `sensitive.*`).

**Ejemplo que lo dispara:**
```lumen
@lumen 1.0
use sensitive.transfer

action pay(supplier, amount):
  mode: fast  # LMN-0040: transfer.money requiere safe
  execute:
    transfer.money(from=company, to=supplier, amount=amount)
```

**Cómo arreglarlo:** No declares `mode: fast` si usas capacidades sensitive. El modo se infiere automáticamente como `safe`.

---

## LMN-0050 — EscalationTimeout

**Descripción:** El humano no respondió a la solicitud de aprobación dentro del tiempo límite configurado.

**Ejemplo que lo dispara:**
```lumen
# Cuando el webhook no responde en 300 segundos
escalation: webhook(url="https://...", timeout=300s)
```

**Cómo arreglarlo:**
- Aumenta el `timeout` si el proceso de aprobación es lento
- Implementa un fallback en el webhook
- Usa `escalation: cli` para aprobaciones interactivas

---

## LMN-0060 — UndoOutsideWindow

**Descripción:** Se intentó deshacer una acción cuya ventana de tiempo de reversibilidad ya expiró.

**Ejemplo que lo dispara:**
```lumen
# Si pay_supplier tenía reversible: 24h y pasaron más de 24h
undo(action_id="abc-123")  # LMN-0060 si ventana expiró
```

**Cómo arreglarlo:**
- Ejecuta `undo()` dentro de la ventana de tiempo declarada
- Consulta `audit.query(reversible=true)` para ver acciones aún deshacibles

---

## LMN-0070 — UndoChainBroken

**Descripción:** Al intentar deshacer una cadena de acciones, una acción dependiente no pudo deshacerse.

**Cómo arreglarlo:**
- Revisa el audit log para identificar qué acción falló: `audit.query(action="undo_failed")`
- Puede requerir intervención manual
- Considera escalación

---

## LMN-0100 — MissingVersionDeclaration

**Descripción:** El programa no comienza con `@lumen X.Y`.

**Ejemplo que lo dispara:**
```lumen
# Falta @lumen 1.0
print "Hello, World"
```

**Cómo arreglarlo:**
```lumen
@lumen 1.0

print "Hello, World"
```

---

## Tabla de referencia rápida

| Código | Nombre | Fase | Modo |
|--------|--------|------|------|
| LMN-0000 | InternalError | Compilador | Todos |
| LMN-0001 | CapabilityNotDeclared | Compilador | Todos |
| LMN-0002 | UnresolvedAmbiguity | Compilador | Safe |
| LMN-0003 | IrreversibleNotDeclared | Compilador | Safe |
| LMN-0010 | SyntaxError | Compilador | Todos |
| LMN-0011 | IndentationError | Compilador | Todos |
| LMN-0020 | ConstantWithoutContext | Compilador | Safe |
| LMN-0030 | TypeMismatch | Compilador | Todos |
| LMN-0040 | ModeViolation | Compilador | Todos |
| LMN-0050 | EscalationTimeout | Runtime | Safe/Flow |
| LMN-0060 | UndoOutsideWindow | Runtime | Safe/Flow |
| LMN-0070 | UndoChainBroken | Runtime | Safe/Flow |
| LMN-0099 | RuntimeError | Runtime | Todos |
| LMN-0100 | MissingVersionDeclaration | Compilador | Todos |
