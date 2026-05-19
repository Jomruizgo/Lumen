# Track C — Stdlib

## Estado actual
- [x] C.1 — Capability base class (`lumen/stdlib/base.py`)
- [x] C.2 — comm.* capabilities (`lumen/stdlib/comm/capabilities.py`)
- [x] C.3 — time.* capabilities (`lumen/stdlib/time/capabilities.py`)
- [x] C.4 — data.* capabilities (`lumen/stdlib/data/capabilities.py`)
- [x] C.5 — sensitive.* capabilities (`lumen/stdlib/sensitive/capabilities.py`)
- [x] C.6 — cli.* capabilities (`lumen/stdlib/cli/capabilities.py`)
- [x] C.7 — web.* capabilities (`lumen/stdlib/web/capabilities.py`)
- [x] C.8 — llm.* capabilities (`lumen/stdlib/llm/capabilities.py`)

## Completado

### C.1 — Capability base class
- `ExecutionContext(mode, dry_run, audit_log, undo_manager, escalation_handler, ...)`
- `Result.ok(value, action_id)`, `Result.fail(error, action_id)`
- `Capability(ABC)`: `execute()`, `undo()`, `describe()`

### C.2 — comm.*
- `CommReadEmail`: IMAP backend, dry_run mock
- `CommSendEmail`: SMTP backend
- `CommSummarizeEmail`: trunca body a max_lines
- `CommNotifyUser`: Windows MessageBox / Linux notify-send
- `CommSendMessage`: webhook adapter

### C.3 — time.*
- `TimeNow`, `TimeWait`, `TimeReadCalendar`, `TimeCreateEvent`, `TimeFindFreetime`
- `_parse_range()`: today/tomorrow/this_week/last_24h

### C.4 — data.*
- `DataReadFile`, `DataWriteFile` (con compensating action para undo)
- `DataParseDocument` (.md/.json/.txt/.csv)
- `DataSearchSemantic` (keyword fallback)
- `DataExtractEntities` (regex: DATE/MONEY/EMAIL)

### C.5 — sensitive.*
- `SensitiveTransferMoney`: requiere escalation approval, registra undo (24h window)
- `SensitiveDeletePermanent`: IRREVERSIBLE, siempre requiere approval
- `SensitiveDeployProduction`: requiere approval, reversible 1h

### C.6 — cli.*
- `CliRun`, `CliPipe`, `CliWrap`

### C.7 — web.*
- `WebFetch` (async GET), `WebPost` (async POST, reversible), `WebServeWebhook` (placeholder)

### C.8 — llm.*
- `LLMAsk`, `LLMClassify`, `LLMExtract`

## Bloqueos
(ninguno)
