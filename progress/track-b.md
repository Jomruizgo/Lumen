# Track B — Runtime

## Estado actual
- [x] B.1 — Interpreter core (`lumen/runtime/interpreter.py`)
- [x] B.2 — Audit log (`lumen/runtime/audit.py`)
- [x] B.3 — Sandbox (`lumen/runtime/sandbox.py`)
- [x] B.4 — Undo system (`lumen/runtime/undo.py`)
- [x] B.5 — Escalation handlers (`lumen/runtime/escalation.py`)
- [x] B.6 — Agent runtime (`lumen/runtime/agent_runtime.py`)
- [x] B.7 — LLM resolver client (`lumen/runtime/llm_client.py`)

## Completado

### B.1 — Interpreter core
- `Interpreter.run(compiled_program) → ExecutionResult` async-first
- Handles: Assignment, IfStatement, ForStatement, MatchStatement, ReturnStatement,
  Pipeline, ExpressionStatement, FunctionCall, CapabilityCall, PrintStatement,
  UndoStatement, AuditLogCall, ActionDecl, FunctionDecl
- `register_capability(name, cap)`, `set_env(name, val)`
- Fixed: `.target` (not `.name`), `.subject` (not `.value`), `.body` (not `.block`)
- CapabilityCall: resolves `.path` tuple to dotted name

### B.2 — Audit log
- `AuditLog.record(event)` → append-only JSONL en `~/.lumen/audit/YYYY-MM-DD.jsonl`
- `AuditLog.query(action, since, status, mode, reversible)` → filtrado
- `compute_program_hash(source)` → `"sha256:" + hexdigest`

### B.3 — Sandbox
- `Sandbox.run(program_source, compiled_data)` con timeout asyncio
- `check_whitelist(capabilities)` — valida caps autorizadas
- `SandboxTimeout`, `CapabilityNotAuthorized` exceptions

### B.4 — Undo system
- `UndoManager.register(action_id, fn, args, window_seconds, deps)`
- `UndoManager.undo(action_id)` — valida ventana, ejecuta en orden inverso
- `UndoOutsideWindowError (LMN-0060)`, `UndoChainBrokenError (LMN-0070)`

### B.5 — Escalation handlers
- `CLIEscalation`: prompt interactivo con opciones a/r/d/c
- `WebhookEscalation`: POST a URL + callback FastAPI local
- `EscalationTimeout (LMN-0050)` con timeout configurable

### B.6 — Agent runtime
- `AgentRuntime.start/stop/status/logs(name)` 
- Estado en `~/.lumen/agents/<name>/state.json` (Windows: `%LOCALAPPDATA%\Lumen\`)
- Restart automático con backoff

### B.7 — LLM resolver client
- `LLMClient.resolve(ambiguous, context, strategies) → Resolution`
- Config desde `~/.lumen/config.toml`, default: `claude --print --model claude-sonnet-4-6`
- Cache en `~/.lumen/cache/`, retry con backoff exponencial

## Bloqueos
(ninguno)
