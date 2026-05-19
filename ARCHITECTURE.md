# ARCHITECTURE.md — Decisiones técnicas

> Todas las decisiones aquí están **cerradas**. No se renegocian durante implementación.

---

## Stack tecnológico definitivo

| Capa | Tecnología | Versión | Razón |
|---|---|---|---|
| Lenguaje host | Python | 3.11+ | Prototipo rápido, suficiente para v1 |
| Type checking | mypy | latest | strict mode obligatorio |
| Parser | lark | 1.1+ | EBNF, soporte LALR, errores detallados |
| Testing | pytest | 7+ | + pytest-cov, pytest-asyncio |
| Linting | ruff | latest | Más rápido que flake8 |
| Formatting | black | latest | Sin opciones, formato único |
| Async | asyncio | stdlib | Para concurrencia en runtime |
| HTTP server | FastAPI | 0.110+ | Para webhook de escalación |
| HTTP client | httpx | latest | Async nativo |
| CLI | typer | latest | Type-hinted, autodoc |
| Serialización | pydantic | 2+ | Validación de tipos en runtime |
| Logging | structlog | latest | JSON estructurado para audit |
| Packaging | PyInstaller | 6+ | Binarios standalone Windows/Linux |

**Reglas inviolables:**
- Toda función pública tiene type hints completos
- mypy strict mode pasa sin excepciones
- Cero dependencias además de las listadas (excepto en stdlib v1)

---

## ADR-001: Lenguaje host Python, no Rust

**Decisión:** Implementación inicial en Python 3.11+.

**Razón:** El objetivo de v1 es validar el modelo del lenguaje, no su performance. Python permite iterar 5x más rápido. El rewrite a Rust queda planeado para v2 cuando el diseño esté validado.

**Consecuencias:**
- El runtime será más lento que un compilado
- Aceptable para v1 (orquestación, no cómputo intensivo)
- Toda la lógica debe ser portable a Rust (sin trucos de Python)

**NO se revisita.**

---

## ADR-002: Parser con lark, no escrito a mano

**Decisión:** Usar la librería `lark` para el parser, con gramática EBNF.

**Razón:** Un parser hecho a mano agregaría 2-3 semanas. Lark da errores detallados, soporta LALR(1) y Earley, y la gramática queda en un archivo separado leíble.

**Consecuencias:**
- Dependencia externa en el compilador
- Performance aceptable (no compitiendo con tsc)
- Gramática vive en `lumen/compiler/grammar.lark`

---

## ADR-003: Tres modos (fast/safe/flow) con un solo compilador

**Decisión:** Un único lenguaje con tres modos. No tres lenguajes separados.

**Razón:** Flow necesita orquestar fast y safe constantemente. Separarlos crearía overhead de interop en cada operación.

**Consecuencias:**
- El parser detecta el modo por capacidades usadas
- Reglas formales en SPEC.md
- Modo `safe` es el default cuando hay ambigüedad sobre cuál usar

**Detección automática de modo:**

```
Capacidad usada → Modo forzado
─────────────────────────────────
transfer.money       → safe
delete.permanent     → safe
deploy.production    → safe
write.production_db  → safe

read.email           → fast (default)
read.file            → fast (default)
calculate.*          → fast (default)
parse.*              → fast (default)

agent / on / watch   → flow
schedule / cron      → flow
```

Si un programa mezcla capacidades de varios modos, el modo del programa es el más restrictivo de los presentes.

---

## ADR-004: AST inmutable, transformaciones devuelven nuevo AST

**Decisión:** Nodos AST son `frozen dataclass` o pydantic models con `model_config = ConfigDict(frozen=True)`.

**Razón:** Múltiples pases (typecheck, resolver, transpile) deben ser puros. Mutación dificulta debugging y paralelización futura.

**Consecuencias:**
- Cada pase recibe AST y devuelve AST nuevo
- Más memoria, pero negligible en programas reales
- Habilita caching de pases

---

## ADR-005: Audit log es append-only JSON Lines

**Decisión:** Cada decisión y ejecución se loggea en `~/.lumen/audit/YYYY-MM-DD.jsonl`.

**Razón:** JSON Lines es trivialmente parseable, append seguro entre procesos, queryable con `jq`.

**Esquema obligatorio por línea:**

```json
{
  "ts": "2026-05-18T14:30:00Z",
  "program": "path/to/program.lumen",
  "program_hash": "sha256:...",
  "event": "decision|execution|resolution|escalation|undo|error",
  "mode": "fast|safe|flow",
  "action_id": "uuid",
  "details": { /* depende del event type */ },
  "confidence": 0.0,
  "reversible": true,
  "human_approved": true
}
```

**No mutar líneas previas, nunca.**

---

## ADR-006: Capacidades son módulos Python en stdlib

**Decisión:** Cada capacidad en `lumen/stdlib/<dominio>/<nombre>.py` exporta una clase con interfaz uniforme.

**Interfaz obligatoria:**

```python
class Capability(ABC):
    name: str                          # "send.email"
    mode: Literal["fast","safe"]      # modo que requiere
    reversible: bool                   # base de reversibilidad
    requires_approval: bool            # si requiere human-in-loop por default
    
    async def execute(self, args: dict, context: ExecutionContext) -> Result:
        ...
    
    async def undo(self, action_id: str, context: ExecutionContext) -> Result:
        ...  # si reversible=False, raises NotReversibleError
    
    def describe(self) -> CapabilityDescription:
        """Para que el LLM entienda qué hace, sin ejecutarla"""
```

**Razón:** Uniformidad permite que el resolver, audit, y undo funcionen sin casos especiales.

---

## ADR-007: Resolver semántico llama al LLM vía CLI

**Decisión:** El resolver invoca el LLM (Claude por default) vía CLI configurable, no hard-coded a una API.

**Razón:** Permite usar cualquier LLM (Claude Code, ollama local, etc.) y desacopla del proveedor.

**Configuración en `~/.lumen/config.toml`:**

```toml
[resolver]
command = "claude"
args = ["--print", "--model", "claude-sonnet-4-6"]
timeout_seconds = 30
max_retries = 2

[resolver.fallback]
command = "echo"
args = ["RESOLUTION_FAILED"]
```

**Interfaz del resolver:**

```python
async def resolve(
    ambiguous_value: str,
    context: dict,
    strategies: list[ResolutionStrategy]
) -> ResolvedValue | EscalationRequired
```

---

## ADR-008: Escalación al humano por CLI o webhook

**Decisión:** Dos canales de escalación, configurables por programa.

**CLI mode:**
```
[LUMEN] Aprobación requerida:
  Acción: transfer $1000 to Pedro García
  Contexto: factura #4521
  Reversible: 24h
  
  [a] Aprobar  [r] Rechazar  [d] Detalles  [c] Cancelar
> 
```

**Webhook mode:**
```http
POST {webhook_url}
Content-Type: application/json

{
  "approval_id": "uuid",
  "action": {...},
  "context": {...},
  "callback_url": "http://localhost:9999/approve/uuid",
  "timeout_seconds": 300
}
```

El programa Lumen declara cuál usar:
```
agent inbox_monitor:
  escalation: webhook(url="https://...")
  # o: escalation: cli
```

Default: CLI.

---

## ADR-009: Sandbox por subprocess + capability whitelist

**Decisión:** Cada ejecución corre en un subprocess Python con capacidades whitelisted explícitamente.

**Implementación:**
- Wrapper subprocess con stdin/stdout JSON
- Variables de entorno limitadas
- Filesystem chroot opcional (solo Linux v1)
- Timeout obligatorio

**Razón:** Aislamiento real, no solo convención. Si el programa intenta usar una capacidad no declarada, el subprocess no la tiene disponible.

---

## ADR-010: Undo basado en compensating actions

**Decisión:** Cada acción reversible registra su "compensating action" antes de ejecutar.

**Ejemplo:**
```python
# Acción original
transfer($1000, from=A, to=B) 
# Compensating action registrada antes:
transfer($1000, from=B, to=A, reason="undo of action_xyz")
```

**Razón:** Más simple que snapshots de estado. Funciona con APIs externas que no permiten rollback real.

**Cadenas de undo:**
- Si acción C depende de B, y B depende de A, deshacer A deshace todo en orden inverso
- Si una compensación falla, se loggea como `undo_failed` y se escala

---

## ADR-011: Versionado del lenguaje sigue SemVer

- v1.0.0: primera versión estable
- Cambios breaking en sintaxis: bump major
- Nuevas capacidades stdlib: bump minor
- Bug fixes: bump patch

**El programa declara la versión que requiere:**
```
@lumen 1.0
agent inbox_monitor: ...
```

---

## ADR-012: Distribución dual

**Decisión:** Distribuir por dos canales en paralelo:

1. **Binario PyInstaller**
   - Windows: `lumen.exe` standalone (incluye Python)
   - Linux: `lumen` ELF standalone
   - macOS: post-v1
   - Descarga directa desde GitHub Releases

2. **Package managers**
   - Windows: `winget install lumen`
   - Linux Debian/Ubuntu: paquete `.deb` via PPA
   - pip: `pip install lumen-lang` (para devs Python)

**Razón:** Binario para usuarios finales (cero deps), pip para devs que ya tienen Python.

---

## ADR-013: Configuración usuario en `~/.lumen/`

```
~/.lumen/
├── config.toml          # Configuración global
├── audit/
│   └── YYYY-MM-DD.jsonl # Audit logs por día
├── undo/
│   └── <action_id>.json # Compensating actions pendientes
├── cache/
│   └── ...              # Cache de resoluciones LLM
└── credentials/         # Tokens, encriptado con clave del OS
    └── email.enc
```

En Windows: `%LOCALAPPDATA%\Lumen\`

---

## ADR-014: Cero tolerancia a "magic strings"

**Decisión:** Todos los identifiers, capacidades, eventos del audit log, etc. son constantes tipadas en código. Cero strings sueltos.

**Razón:** Refactoring seguro, autocompletado, errores de typo detectados por mypy.

**Ejemplo:**
```python
# NO
log.write("execution")

# SÍ
log.write(AuditEvent.EXECUTION)
```

---

## ADR-015: Errores tienen códigos y son documentables

**Decisión:** Cada error de compilación o runtime tiene un código `LMN-NNNN`.

**Catálogo en `docs/errors.md`:**

```
LMN-0001: Capacidad usada sin declarar
LMN-0002: Ambigüedad sin estrategia de resolución
LMN-0003: Acción irreversible sin declarar reversible: false
LMN-0010: Sintaxis inválida
...
```

Mensajes de error incluyen:
- Código
- Mensaje claro
- Posición exacta (archivo, línea, columna)
- Sugerencia accionable
- Link al doc del error

**Razón:** LLMs pueden googlear códigos. Humanos pueden buscarlos en docs. Tests pueden assertar sobre códigos, no sobre texto.

---

## Estructura de un pase del compilador

Todos los pases siguen la misma estructura:

```python
class CompilerPass(ABC):
    name: str
    requires: list[type[CompilerPass]]  # pases que deben correr antes
    
    @abstractmethod
    def run(self, ast: AST, ctx: CompilerContext) -> AST | list[CompilerError]:
        ...
```

**Pases en orden:**
1. Lexer (texto → tokens)
2. Parser (tokens → AST sin resolver)
3. ModeDetector (decide fast/safe/flow)
4. CapabilityChecker (verifica capacidades declaradas vs usadas)
5. TypeChecker (inferencia y verificación)
6. Resolver (resuelve ambigüedades, puede llamar LLM/humano)
7. ReversibilityChecker (verifica que irreversibles tengan aprobación)
8. AuditInjector (inyecta logging en cada nodo)
9. Transpiler (AST → Python ejecutable)

Cada pase es independiente y testeable.

---

## Decisiones explícitamente NO tomadas (para v2)

- Sistema de plugins de capacidades (v1: stdlib fija)
- Compilación a Rust o WASM
- IDE integration (LSP)
- REPL interactivo
- Distributed execution (multi-host)
- Foreign function interface a otros lenguajes

Estas se evalúan después de v1.

---

## Siguiente paso

Lee `SPEC.md` para la especificación formal del lenguaje.
