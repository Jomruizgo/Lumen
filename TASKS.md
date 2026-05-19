# TASKS.md — Tareas atómicas por track

> Cada tarea tiene: ID, dependencias, input contract, output contract, criterio de aceptación ejecutable.
> 
> **Regla:** No avanzar a la siguiente tarea sin que el criterio de aceptación pase.

---

## Convenciones para todas las tareas

- Todo código en `lumen/` package
- Tests en `tests/<modulo>/test_<archivo>.py`
- Type hints estrictos, `mypy --strict` debe pasar
- Docstrings en cada función pública (Google style)
- Errores con código `LMN-XXXX` y mensaje claro

---

# TRACK A — Compiler

**Asignar a:** instancia de Claude Code dedicada.
**Dependencias:** ninguna, puede empezar inmediatamente.
**Duración estimada:** 6 semanas.

---

## A.1 — Project scaffold

**Dependencias:** ninguna

**Output:**
- `pyproject.toml` con dependencias de ARCHITECTURE.md
- Estructura de directorios completa (ver README.md sección "Estructura final")
- `lumen/__init__.py` con `__version__ = "0.1.0"`
- CLI vacío en `lumen/cli.py` usando typer
- `pre-commit` configurado: ruff, black, mypy strict
- `.github/workflows/ci.yml` corriendo tests + mypy

**Criterio de aceptación:**
```bash
poetry install
mypy --strict lumen/
pytest tests/ -v          # 0 tests, debe pasar
lumen --version           # imprime 0.1.0
```

---

## A.2 — Lexer

**Dependencias:** A.1

**Input contract:**
- Función `tokenize(source: str) -> list[Token] | LexError`
- `Token = dataclass(type: TokenType, value: str, line: int, col: int)`
- `TokenType = Enum(...)` con todos los tokens de SPEC.md sección 15

**Output contract:**
- Reconoce keywords: action, agent, fn, use, import, if, else, match, for, return, resolve, because, mode, requires, execute, reversible, audit, watch, on, state, config, schedule, true, false
- Identificadores: `[a-zA-Z_][a-zA-Z0-9_]*`
- Números (int, float)
- Strings con interpolación `"${x}"`
- Operadores: `+ - * / | -> => > < >= <= == != = ?`
- Delimitadores: `( ) { } [ ] , : .`
- Time literals: `5min`, `2h`, `7d`
- Money literals: `$100 USD`, `€50 EUR`
- Comentarios: `#`
- Indentación: emite `INDENT` / `DEDENT` (2 espacios)

**Tests obligatorios en `tests/compiler/test_lexer.py`:**
```python
def test_tokenizes_keywords()
def test_tokenizes_identifiers()
def test_tokenizes_numbers_int_and_float()
def test_tokenizes_strings_with_interpolation()
def test_tokenizes_money_literals()
def test_tokenizes_time_literals()
def test_emits_indent_dedent_correctly()
def test_handles_comments()
def test_lex_error_invalid_char_returns_LexError_with_position()
def test_50_fixtures_in_fixtures_dir()   # 50 fixtures pre-creados
```

**Criterio de aceptación:**
```bash
pytest tests/compiler/test_lexer.py -v --cov=lumen/compiler/lexer --cov-fail-under=90
```

---

## A.3 — AST nodes

**Dependencias:** A.1

**Output contract:**
- `lumen/compiler/ast_nodes.py` con todas las clases del AST
- Todas son `pydantic.BaseModel` con `model_config = ConfigDict(frozen=True)`
- Cada nodo tiene: `position: SourcePosition`
- Método `pretty_print(indent=0) -> str` en cada nodo

**Clases obligatorias:**
```
Program, VersionDecl
CapabilityDecl, ImportDecl
AgentDecl, ActionDecl, FunctionDecl
WatchClause, OnClause, ScheduleClause, ConfigClause, StateClause
RequiresClause, ExecuteClause, ReversibleClause, AuditClause
Param, Block, Pipeline, Assignment
IfStatement, MatchStatement, ForStatement, ReturnStatement
ResolveBlock, StrategyClause
Expression, BinaryOp, FunctionCall, CapabilityCall
Literal, NumberLiteral, StringLiteral, BooleanLiteral, TimeLiteral, MoneyLiteral
Identifier, StringInterpolation
Type, PrimitiveType, ParametrizedType, UnionType
BecauseAnnotation
```

**Criterio de aceptación:**
```bash
pytest tests/compiler/test_ast_nodes.py -v
# Test: cada clase es instanciable, frozen, serializable a JSON
# Test: pretty_print produce output legible
```

---

## A.4 — Parser

**Dependencias:** A.2, A.3

**Input contract:**
- `parse(tokens: list[Token]) -> Program | ParseError`
- Gramática en `lumen/compiler/grammar.lark` siguiendo EBNF de SPEC.md sección 3
- Usa lark con LALR(1)

**Output contract:**
- Construye AST tipado completo
- Errores con código `LMN-0010` o `LMN-0011` y posición exacta
- Mensajes de error incluyen sugerencia accionable cuando es posible

**Tests obligatorios:**
```python
def test_parses_all_15_canonical_examples()  # de EXAMPLES.md
def test_parses_empty_program_with_just_version()
def test_parser_error_includes_position()
def test_parser_error_includes_suggestion()
def test_indentation_error_detected()
def test_50_synthetic_programs_parse()
```

**Criterio de aceptación:**
```bash
pytest tests/compiler/test_parser.py -v
# Y específicamente:
python -c "
from lumen.compiler.lexer import tokenize
from lumen.compiler.parser import parse
import os
for f in os.listdir('examples/'):
    if f.endswith('.lumen'):
        with open(f'examples/{f}') as fp:
            tokens = tokenize(fp.read())
            ast = parse(tokens)
            assert not isinstance(ast, Exception), f'{f} failed'
print('OK')
"
```

---

## A.5 — Mode detector

**Dependencias:** A.4

**Input contract:**
- `detect_mode(ast: Program) -> Literal["fast", "safe", "flow"]`

**Output contract:**
- Sigue las reglas de ARCHITECTURE.md ADR-003
- Si programa tiene `agent`, `on`, `watch`, `schedule` → `flow`
- Si usa capacidades sensitive.* o reversible:false → `safe`
- Si declara `mode: safe` explícito → `safe`
- Default → `fast`
- Si declara `mode: fast` pero usa capacidad que requiere safe → error `LMN-0040`

**Tests obligatorios:**
```python
def test_detects_fast_for_pure_computation()
def test_detects_safe_for_transfer_money()
def test_detects_flow_for_agent_with_watch()
def test_explicit_safe_overrides_fast_inference()
def test_explicit_fast_fails_if_safe_required()
```

**Criterio de aceptación:**
```bash
pytest tests/compiler/test_mode_detector.py -v --cov-fail-under=95
```

---

## A.6 — Capability checker

**Dependencias:** A.4

**Input contract:**
- `check_capabilities(ast: Program) -> list[CompileError]`

**Output contract:**
- Verifica que cada `CapabilityCall` esté declarada en `CapabilityDecl`
- Cada capacidad sin declarar produce error `LMN-0001`
- Soporta aliasing (`use comm.email as mail`)

**Tests obligatorios:**
```python
def test_passes_when_all_capabilities_declared()
def test_error_when_using_undeclared_capability()
def test_error_includes_capability_name_and_suggestion()
def test_aliasing_works()
```

**Criterio de aceptación:**
```bash
pytest tests/compiler/test_capability_checker.py -v
```

---

## A.7 — Type checker

**Dependencias:** A.3, A.4

**Input contract:**
- `typecheck(ast: Program) -> TypedProgram | list[TypeError]`
- `TypedProgram` es un AST donde cada expresión tiene `inferred_type`

**Output contract:**
- Inferencia de tipos para literales, expresiones binarias, llamadas
- Verifica tipos en parámetros de funciones cuando están anotados
- Money con currencies distintas no se suman → `LMN-0030`
- Soporta tipos paramétricos (`Maybe<T>`, `List<T>`, etc.)
- Soporta tipos unión

**Tests obligatorios:**
```python
def test_infers_number_for_arithmetic()
def test_infers_text_for_strings()
def test_money_same_currency_addable()
def test_money_different_currency_fails()
def test_parametric_types_propagate()
def test_union_types_in_function_signature()
```

**Criterio de aceptación:**
```bash
pytest tests/compiler/test_typecheck.py -v --cov-fail-under=85
```

---

## A.8 — Resolver semántico

**Dependencias:** A.7

**Input contract:**
- `resolve(ast: TypedProgram, llm_client: LLMClient | None) -> ResolvedProgram | list[ResolutionError]`
- `llm_client` puede ser `None` en modo dry-run
- En modo dry-run, las resoluciones quedan marcadas como `Pending`

**Output contract:**
- Identifica todos los nodos `ResolveBlock`
- Para cada uno, llama al LLM con contexto
- Aplica estrategias en orden: `high_confidence` → `ambiguous` → `unknown`
- Si confianza alta y `high_confidence` declarado, resuelve directo
- Si necesita usuario, marca como `EscalationRequired`
- Si `unknown` y solo hay `fail_safe`, retorna error
- En modo safe, todo `ResolveBlock` debe tener `ambiguous` y `unknown` → si no, error `LMN-0002`

**Tests obligatorios:**
```python
def test_high_confidence_resolves_directly()
def test_ambiguous_triggers_escalation()
def test_unknown_falls_through_to_fail_safe()
def test_safe_mode_requires_ambiguous_and_unknown_clauses()
def test_dry_run_marks_as_pending_without_calling_llm()
def test_20_resolution_scenarios()  # fixtures
```

**Criterio de aceptación:**
```bash
pytest tests/compiler/test_resolver.py -v
```

---

## A.9 — Reversibility checker

**Dependencias:** A.7

**Input contract:**
- `check_reversibility(ast: TypedProgram) -> list[CompileError]`

**Output contract:**
- Acciones con capacidad irreversible deben declarar `reversible: false` explícitamente → si no, error `LMN-0003`
- Acciones en modo safe DEBEN tener cláusula `reversible:`
- Pipelines heredan la reversibilidad mínima
- `reversible: <duration>` requiere duration parseable

**Tests obligatorios:**
```python
def test_safe_action_must_declare_reversibility()
def test_irreversible_capability_requires_explicit_false()
def test_pipeline_reversibility_is_minimum()
def test_duration_format_validated()
```

**Criterio de aceptación:**
```bash
pytest tests/compiler/test_reversibility.py -v
```

---

## A.10 — Audit injector

**Dependencias:** A.9

**Input contract:**
- `inject_audit(ast: ResolvedProgram) -> InstrumentedProgram`

**Output contract:**
- Inyecta nodos `AuditLogCall` antes y después de cada acción según nivel declarado
- `audit: full` → log de decisión, ejecución, resultado
- `audit: minimal` → solo ejecución
- `audit: silent` → nada (solo modo fast)
- Default por modo según SPEC.md sección 8.2

**Tests obligatorios:**
```python
def test_full_audit_injects_all_three_events()
def test_minimal_audit_injects_only_execution()
def test_silent_audit_injects_nothing()
def test_safe_mode_cannot_be_silent()
```

**Criterio de aceptación:**
```bash
pytest tests/compiler/test_audit_injector.py -v
```

---

## A.11 — Pipeline orchestrator

**Dependencias:** A.10

**Input contract:**
- Clase `CompilerPipeline` que orquesta todos los pases
- Método `compile(source: str) -> CompiledProgram | list[CompileError]`

**Output contract:**
- Ejecuta pases en orden: lex → parse → detect_mode → check_caps → typecheck → resolve → check_rev → inject_audit
- Detiene en el primer pase que produce errores
- Retorna todos los errores del pase fallido (no solo el primero)

**Criterio de aceptación:**
```bash
pytest tests/compiler/test_pipeline.py -v
# Y:
python -c "
from lumen.compiler.pipeline import CompilerPipeline
import os
for f in os.listdir('examples/'):
    if f.endswith('.lumen'):
        with open(f'examples/{f}') as fp:
            result = CompilerPipeline().compile(fp.read())
            print(f, type(result).__name__)
"
# Todos los ejemplos deben producir CompiledProgram, no errores
```

---

## A.12 — Documentar errores

**Dependencias:** todas las anteriores (errores ya definidos)

**Output:**
- `docs/errors.md` con todos los códigos `LMN-XXXX` usados
- Cada código tiene: descripción, ejemplo de código que lo dispara, cómo arreglarlo

**Criterio de aceptación:**
```bash
python tests/docs_completeness.py
# Verifica que cada código LMN-XXXX usado en código fuente existe en docs/errors.md
```

---

# TRACK B — Runtime

**Asignar a:** instancia de Claude Code dedicada.
**Dependencias:** A.3 (AST), A.11 (compiler pipeline).
**Duración estimada:** 5 semanas (en paralelo con C y D).

---

## B.1 — Interpreter core

**Dependencias:** A.11

**Input contract:**
- `Interpreter.run(program: CompiledProgram, context: ExecutionContext) -> ExecutionResult`
- `ExecutionContext = dataclass(capabilities: dict, audit_log: AuditLog, ...)`

**Output contract:**
- Interpreta directamente el AST (no transpila a Python para v1)
- Soporta todos los statements de SPEC.md
- Async-first: todas las capability calls son `await`
- Resultados como `Result<T, E>`, errores como valores

**Tests obligatorios:**
```python
def test_runs_hello_world()
def test_runs_function_call()
def test_runs_pipeline()
def test_runs_if_else()
def test_runs_match()
def test_runs_for_loop()
def test_propagates_errors_with_question_mark()
def test_runs_all_15_examples_with_mocked_capabilities()
```

**Criterio de aceptación:**
```bash
pytest tests/runtime/test_interpreter.py -v --cov-fail-under=85
```

---

## B.2 — Audit log

**Dependencias:** A.10

**Input contract:**
- Clase `AuditLog` con métodos `record(event: AuditEvent)`, `query(...) -> list[AuditEvent]`
- Archivos en `~/.lumen/audit/YYYY-MM-DD.jsonl` (Windows: `%LOCALAPPDATA%\Lumen\audit\`)
- Append-only, JSON Lines

**Output contract:**
- Schema según ARCHITECTURE.md ADR-005
- Query soporta filtros: action, since, status, mode
- Thread-safe (multiple agents pueden escribir simultáneamente)

**Tests obligatorios:**
```python
def test_records_event()
def test_appends_does_not_overwrite()
def test_queries_by_action()
def test_queries_by_time_range()
def test_thread_safe_concurrent_writes()
def test_works_on_windows_paths()
```

**Criterio de aceptación:**
```bash
pytest tests/runtime/test_audit.py -v
```

---

## B.3 — Sandbox

**Dependencias:** B.1

**Input contract:**
- Clase `Sandbox` que ejecuta `CompiledProgram` en subprocess aislado
- Whitelist de capacidades pasada como parámetro
- Timeout obligatorio

**Output contract:**
- Subprocess Python con stdin/stdout JSON
- Variables de entorno limitadas (solo PATH y específicas declaradas)
- Si el programa intenta usar capacidad no autorizada → falla con `CapabilityNotAuthorized`
- Captura stdout/stderr estructurado

**Tests obligatorios:**
```python
def test_runs_program_in_subprocess()
def test_capability_whitelist_enforced()
def test_timeout_kills_runaway()
def test_captures_output_structured()
def test_isolates_filesystem_writes_on_linux()
```

**Criterio de aceptación:**
```bash
pytest tests/runtime/test_sandbox.py -v
```

---

## B.4 — Undo system

**Dependencias:** B.2

**Input contract:**
- Clase `UndoManager` con métodos:
  - `register(action_id, compensating_action, window)`
  - `undo(action_id) -> Result`
  - `list_reversible(since)`

**Output contract:**
- Compensating actions persistidas en `~/.lumen/undo/<action_id>.json`
- Verifica ventana de tiempo antes de ejecutar undo
- Si compensating action falla → loggea `undo_failed` y escala
- Cadenas: si A causó B, deshacer A deshace B primero

**Tests obligatorios:**
```python
def test_registers_compensating_action()
def test_undo_within_window_succeeds()
def test_undo_outside_window_fails()
def test_undo_chain_executes_in_reverse_order()
def test_failed_compensation_escalates()
```

**Criterio de aceptación:**
```bash
pytest tests/runtime/test_undo.py -v
```

---

## B.5 — Escalation handlers

**Dependencias:** B.1

**Input contract:**
- Interfaz `EscalationHandler` con método async `request_approval(request) -> ApprovalResponse`
- Dos implementaciones: `CLIEscalation`, `WebhookEscalation`

**Output contract:**

**CLIEscalation:**
- Imprime detalles, lee respuesta del stdin
- Opciones: aprobar, rechazar, ver detalles, cancelar
- Timeout configurable

**WebhookEscalation:**
- POST a URL configurada con payload de ARCHITECTURE.md ADR-008
- Servidor local recibe callback en puerto efímero
- Timeout configurable

**Tests obligatorios:**
```python
def test_cli_approval_with_simulated_input()
def test_cli_timeout()
def test_webhook_posts_request()
def test_webhook_receives_callback()
def test_webhook_timeout()
```

**Criterio de aceptación:**
```bash
pytest tests/runtime/test_escalation.py -v
```

---

## B.6 — Agent runtime

**Dependencias:** B.1, B.2

**Input contract:**
- `AgentRuntime.start(agent_decl, context)` → subprocess persistente
- `AgentRuntime.stop(name)`, `status(name)`, `logs(name)`

**Output contract:**
- Cada agent corre en subprocess separado
- Estado persistido en `~/.lumen/agents/<name>/state.json`
- Watch clauses se polean según `poll_interval` config
- Schedule clauses usan cron syntax
- Reinicia automáticamente si falla (max 3 retries por hora)

**Tests obligatorios:**
```python
def test_starts_agent_as_subprocess()
def test_persists_state_between_events()
def test_polls_watch_clause()
def test_executes_schedule_clause()
def test_auto_restart_on_failure()
def test_stop_kills_subprocess()
```

**Criterio de aceptación:**
```bash
pytest tests/runtime/test_agent.py -v
```

---

## B.7 — LLM resolver client

**Dependencias:** B.1

**Input contract:**
- Clase `LLMClient` configurable via `~/.lumen/config.toml`
- Método async `resolve(ambiguous: str, context: dict, strategies: list) -> Resolution`

**Output contract:**
- Invoca LLM via CLI (default: `claude`) según ADR-007
- Cache de resoluciones en `~/.lumen/cache/`
- Retry con exponential backoff
- Fallback si LLM no disponible

**Tests obligatorios:**
```python
def test_invokes_configured_cli()
def test_caches_resolutions()
def test_retries_on_failure()
def test_fallback_when_unavailable()
```

**Criterio de aceptación:**
```bash
pytest tests/runtime/test_llm_client.py -v
```

---

# TRACK C — Stdlib

**Asignar a:** instancia de Claude Code dedicada.
**Dependencias:** B.1 (interpreter), B.2 (audit), B.5 (escalation).
**Duración estimada:** 4 semanas (en paralelo con B y D después de B.1).

---

## C.1 — Capability base class

**Dependencias:** B.1

**Output:**
- `lumen/stdlib/base.py` con clase `Capability` abstracta según ARCHITECTURE.md ADR-006

**Criterio de aceptación:**
```bash
pytest tests/stdlib/test_base.py -v
```

---

## C.2 — comm.* capabilities

**Dependencias:** C.1

**Capacidades a implementar:**
- `read.email(filter)` — IMAP backend, mockable
- `send.email(to, subject, body)` — SMTP backend
- `summarize.email(email, max_lines)` — usa llm.ask internamente
- `send.message(channel, recipient, text)` — adapter para Slack/Telegram
- `notify.user(text, priority)` — notificación nativa (Windows toast / Linux libnotify)
- `speak.text(text)` — TTS (Windows SAPI / espeak)
- `listen.user(timeout)` — STT (con whisper local o input CLI)

Cada una con:
- Tests con backend mockeado
- Configuración via `~/.lumen/credentials/`
- Soporte para email providers comunes (Gmail, Outlook IMAP)

**Criterio de aceptación:**
```bash
pytest tests/stdlib/comm/ -v --cov-fail-under=80
```

---

## C.3 — time.* capabilities

**Dependencias:** C.1

**Capacidades:**
- `read.calendar(range)` — Google Calendar API, mockeable
- `create.event(...)` — idem
- `find.freetime(duration, range)` — calcula desde calendar
- `now()` — timezone-aware
- `wait(duration)` — async sleep

**Criterio de aceptación:**
```bash
pytest tests/stdlib/time/ -v
```

---

## C.4 — data.* capabilities

**Dependencias:** C.1

**Capacidades:**
- `read.file(path)` — async, soporta text y binary
- `write.file(path, content)` — con compensating action (delete) para undo
- `parse.document(path)` — PDF, DOCX, MD, HTML
- `search.semantic(query, corpus)` — usa embeddings (sentence-transformers local)
- `extract.entities(text, types)` — NER con spaCy

**Criterio de aceptación:**
```bash
pytest tests/stdlib/data/ -v
```

---

## C.5 — sensitive.* capabilities

**Dependencias:** C.1, B.4 (undo), B.5 (escalation)

**Capacidades:**
- `transfer.money(from, to, amount)` — sin backend real, simulado para tests + interface para que el usuario conecte su banco
- `delete.permanent(path)` — siempre requiere aprobación
- `deploy.production(system, version)` — webhook a sistema externo

Cada una:
- `requires_approval: True` por default
- Loggeo full obligatorio
- Compensating action registrada cuando aplica

**Criterio de aceptación:**
```bash
pytest tests/stdlib/sensitive/ -v
```

---

## C.6 — cli.* capabilities

**Dependencias:** C.1

**Capacidades:**
- `cli.run(command, args)` — subprocess seguro
- `cli.pipe(commands)` — pipeline de comandos
- `cli.wrap(binary_path)` — crea capability nueva desde un CLI

**Implementación de wrap:**
- Parsea `--help` para extraer flags
- Genera signature de capability
- Auto-doc

**Criterio de aceptación:**
```bash
pytest tests/stdlib/cli/ -v
# Y específicamente:
python -c "
from lumen.stdlib.cli import wrap
git_cap = wrap('git')
assert 'log' in git_cap.subcommands
"
```

---

## C.7 — web.* capabilities

**Dependencias:** C.1

**Capacidades:**
- `fetch.url(url)` — async GET
- `post.url(url, body)` — POST con compensating action si aplica
- `serve.webhook(port, handler)` — FastAPI server local

**Criterio de aceptación:**
```bash
pytest tests/stdlib/web/ -v
```

---

## C.8 — llm.* capabilities

**Dependencias:** C.1, B.7

**Capacidades:**
- `llm.ask(prompt, context)` — query libre
- `llm.classify(input, categories)` — clasificación con confianza
- `llm.extract(text, schema)` — extracción estructurada

Todas usan el LLMClient configurado.

**Criterio de aceptación:**
```bash
pytest tests/stdlib/llm/ -v
```

---

# TRACK D — Tooling, Tests, Docs, Distribución

**Asignar a:** instancia de Claude Code dedicada.
**Dependencias:** SPEC.md (puede empezar inmediatamente con ejemplos y docs).
**Duración estimada:** 5 semanas en paralelo con todos los demás.

---

## D.1 — Crear los 15 programas de ejemplo

**Dependencias:** SPEC.md

**Output:**
- `examples/01_hello.lumen` a `examples/15_scheduled_agent.lumen`
- Cada uno exactamente como en EXAMPLES.md
- `examples/README.md` describiendo cada uno

**Criterio de aceptación:**
- Los 15 archivos existen
- Pasan revisión manual contra EXAMPLES.md

---

## D.2 — Test fixtures para lexer y parser

**Dependencias:** SPEC.md

**Output:**
- `tests/compiler/fixtures/lexer/` con 50 archivos (valid + invalid)
- `tests/compiler/fixtures/parser/` con 50 archivos
- `tests/compiler/fixtures/typecheck/` con 30 archivos
- Cada fixture tiene `.lumen` + `.expected` (resultado esperado)

**Criterio de aceptación:**
- 130 fixtures totales
- Cada uno tiene su `.expected` correspondiente

---

## D.3 — Formatter

**Dependencias:** A.4 (parser)

**Input contract:**
- `format(source: str) -> str`
- CLI: `lumen fmt <file>` o `lumen fmt --check <file>`

**Output contract:**
- Formato único, sin opciones
- Indentación 2 espacios
- Espacios alrededor de operadores
- Pipelines con `|` al inicio de línea
- Strings con comillas dobles
- Idempotente: `format(format(x)) == format(x)`

**Criterio de aceptación:**
```bash
pytest tests/tooling/test_format.py -v
# Test: format(format(x)) == format(x) para 100 programas
```

---

## D.4 — Explain mode

**Dependencias:** A.7 (typecheck)

**Input contract:**
- CLI: `lumen explain <file>`
- Output: explicación en lenguaje natural

**Output contract:**
- Lista capacidades usadas
- Lista decisiones implícitas (modo detectado, reversibilidad)
- Marca operaciones irreversibles
- Sugiere mejoras (si aplica)

**Criterio de aceptación:**
```bash
pytest tests/tooling/test_explain.py -v
```

---

## D.5 — Dry-run mode

**Dependencias:** A.11

**Input contract:**
- CLI: `lumen run --dry-run <file>`

**Output contract:**
- Compila el programa
- Resuelve ambigüedades en modo "pending" (sin ejecutar LLM real)
- Muestra plan de ejecución paso a paso
- No toca filesystem, red, ni audit log

**Criterio de aceptación:**
```bash
pytest tests/tooling/test_dryrun.py -v
```

---

## D.6 — Documentación: manual del lenguaje

**Dependencias:** SPEC.md

**Output:**
- `docs/manual.md` — manual completo, optimizado para LLMs
- `docs/patterns.md` — 30 patrones canónicos con nombre
- `docs/pitfalls.md` — errores comunes y cómo evitarlos
- `docs/agent_prompt.md` — system prompt completo para LLMs constructores

**Criterio de aceptación:**
- Otro LLM con solo `agent_prompt.md` debe generar correctamente 9/10 programas para prompts de prueba

---

## D.7 — Benchmark de tokens

**Dependencias:** Track A y B funcionando

**Output:**
- `tests/benchmarks/token_efficiency.py`
- Implementa las 10 tareas canónicas de EXAMPLES.md sección "Programas de benchmark"
- Cuenta tokens (con tiktoken) de:
  - Solución en Python
  - Solución en Lumen
  - Mismo prompt enviado a un LLM, midiendo tokens generados

**Criterio de aceptación:**
- Reporte muestra ratio Lumen/Python ≤ 0.5 en promedio

---

## D.8 — Benchmark de corrección

**Dependencias:** Track A y B funcionando

**Output:**
- `tests/benchmarks/correctness.py`
- 50 prompts naturales
- Llama al LLM dos veces: pidiendo Python, pidiendo Lumen
- Ejecuta ambas soluciones, mide si pasan tests
- Reporta tasa de éxito al primer intento

**Criterio de aceptación:**
- Lumen ≥ 20% más éxito al primer intento

---

## D.9 — Instalador Windows

**Dependencias:** todo lo anterior funcionando

**Output:**
- `installer/windows/build.py` — script PyInstaller
- Genera `lumen.exe` standalone (≤100MB)
- Incluye Python embebido + todas las deps
- Manifest para `winget`

**Criterio de aceptación:**
```powershell
cd installer/windows
python build.py
.\dist\lumen.exe --version          # imprime versión
.\dist\lumen.exe run ..\..\examples\01_hello.lumen
```

---

## D.10 — Instalador Linux

**Dependencias:** todo lo anterior funcionando

**Output:**
- `installer/linux/Makefile`
- Genera `lumen` ELF standalone con PyInstaller
- Paquete `.deb` con dependencias declaradas
- Script de instalación: `curl ... | sh`

**Criterio de aceptación:**
```bash
cd installer/linux
make
./build/lumen --version
./build/lumen run ../../examples/01_hello.lumen
```

---

## D.11 — CI/CD pipeline

**Dependencias:** todo lo anterior

**Output:**
- `.github/workflows/test.yml` — corre tests en push (Windows + Linux)
- `.github/workflows/release.yml` — genera binarios en tag `v*`
- Coverage report a Codecov
- Validación de mypy strict

**Criterio de aceptación:**
- Push de un tag `v1.0.0-rc1` genera releases con binarios Windows y Linux

---

## D.12 — End-to-end test suite

**Dependencias:** todos los tracks

**Output:**
- `tests/e2e/test_full_examples.py`
- Ejecuta los 15 ejemplos con mocks de capacidades
- Verifica: ejecución correcta, audit log correcto, errores correctos en tests negativos

**Criterio de aceptación:**
```bash
pytest tests/e2e/ -v
# 15 ejemplos verdes + 30 casos negativos verdes
```

---

# Coordinación entre tracks

## Sincronización obligatoria

| Punto | Quién espera a quién |
|---|---|
| B.1 empezar | A.3 (AST) y A.11 (pipeline) terminados |
| C.1 empezar | B.1 terminado |
| C.5 empezar | C.1, B.4, B.5 terminados |
| D.7/D.8 empezar | B.1 y C.* funcionando |
| D.9/D.10 empezar | Todos los anteriores terminados |

## Reuniones de sync (entre agentes)

Cada track al terminar una tarea publica en `progress/track-X.md`:
- Tarea completada
- Cualquier cambio a interfaces compartidas
- Bloqueos detectados

Antes de empezar una tarea, leer `progress/` de todos los tracks.

---

# Definition of Done global (repite del README)

El lenguaje está terminado cuando:

```bash
pytest tests/ --cov=lumen --cov-fail-under=80
lumen run examples/canonical/*.lumen --check-only
python tests/benchmarks/token_efficiency.py --threshold=0.5
python tests/benchmarks/correctness.py --threshold=0.9
cd installer/windows && python build.py && ./dist/lumen.exe --version
cd installer/linux && make && ./build/lumen --version
```

Los 6 comandos retornan exit code 0.

---

# Hito final post-Lumen v1

Una vez que los 6 comandos pasan, **abrir una sesión nueva de Claude Code** con este prompt:

```
Eres un desarrollador Lumen. Lee:
- docs/manual.md
- docs/patterns.md
- docs/agent_prompt.md

NO leas el código fuente del compilador.

Construye una aplicación: asistente personal que monitorea correos, 
lee mi agenda y me da un resumen cada mañana a las 8am. 
Decisiones importantes deben requerir mi aprobación.

Usa solo el lenguaje Lumen.
```

Si el agente construye una app que corre 7 días sin errores críticos, **Lumen está validado**.
