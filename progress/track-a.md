# Track A — Compiler

## Estado actual
- [x] A.1 — Project scaffold (completo)
- [x] A.2 — Lexer (`lumen/compiler/lexer.py`, 645 líneas)
- [x] A.3 — AST nodes (`lumen/compiler/ast_nodes.py`, 705 líneas, pydantic frozen)
- [x] A.4 — Parser (`lumen/compiler/parser.py`, 1492 líneas, recursive descent)
- [x] A.5 — Mode detector (`lumen/compiler/mode_detector.py`)
- [x] A.6 — Capability checker (`lumen/compiler/cap_checker.py`, LMN-0001)
- [x] A.7 — Type checker (`lumen/compiler/typechecker.py`, LMN-0020/0030)
- [x] A.8 — Resolver semántico (`lumen/compiler/resolver.py`, LMN-0002)
- [x] A.9 — Reversibility checker (`lumen/compiler/rev_checker.py`, LMN-0003/0040)
- [x] A.10 — Audit injector (`lumen/compiler/audit_injector.py`)
- [x] A.11 — Pipeline orchestrator (`lumen/compiler/pipeline.py`, `CompilerPipeline`, `CompiledProgram`)
- [x] A.12 — Documentar errores (`docs/errors.md`)

## Completado

### A.2 — Lexer
Tokenizer completo con todos los `TokenType`. Maneja INDENT/DEDENT, interpolación, money, time, capabilities.

### A.3 — AST nodes
705 líneas. Todos los nodos como `pydantic.BaseModel(frozen=True)`. Incluye `AuditLogCall` para el injector.

### A.4 — Parser
1492 líneas. Recursive descent, retorna `Program | ParseError`. Parsea todas las construcciones del lenguaje.

### A.5 — Mode detector
`detect_mode(program) → ModeResult | CompileError`. 6 reglas en orden de prioridad. Detecta fast/safe/flow.

### A.6 — Capability checker
`check_capabilities(program) → list[CompileError]`. Emite LMN-0001 para capabilities no declaradas con `use`.

### A.7 — Type checker
`typecheck(program, mode) → TypedProgram | list[CompileError]`. Inferencia básica. LMN-0030 (TypeMismatch), LMN-0020 (ConstantWithoutContext en safe mode).

### A.8 — Resolver semántico
`resolve_semantics(typed, mode) → ResolvedProgram | list[CompileError]`. Valida estrategias `resolve()`. LMN-0002.

### A.9 — Reversibility checker
`check_reversibility(program) → list[CompileError]`. LMN-0003/LMN-0040 para caps irreversibles sin declaración.

### A.10 — Audit injector
`inject_audit(resolved, mode) → InstrumentedProgram`. Inyecta `AuditLogCall` en actions. Usa `model_copy()` (AST frozen).

### A.11 — Pipeline orchestrator
`CompilerPipeline.compile(source) → CompileResult`. 7 passes en orden. Acumula todos los errores posibles.
`CompiledProgram.instrumented.resolved.typed.ast` → `Program` para el intérprete.

### A.12 — Error catalog
`docs/errors.md` con todos los códigos LMN-0001 a LMN-0100.

## Bloqueos
(ninguno)
