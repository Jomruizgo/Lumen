# Track D — Tooling, Tests, Docs, Distribución

## Estado actual
- [x] D.1 — 15 programas de ejemplo (`examples/01_hello.lumen` … `examples/15_scheduled_agent.lumen` + `examples/README.md`)
- [x] D.2 — Test fixtures para lexer y parser (50 lexer + 50 parser + 30 typecheck = 130 fixtures, 260 archivos)
- [x] D.3 — Formatter (`lumen/tooling/format.py` — regex-based, idempotent)
- [x] D.4 — Explain mode (`lumen/tooling/explain.py` — usa compilador real, fallback regex)
- [x] D.5 — Dry-run mode (`lumen/tooling/dryrun.py` — usa compilador real, fallback regex)
- [x] D.6 — Documentación: manual del lenguaje (`docs/manual.md`, `docs/patterns.md`, `docs/pitfalls.md`, `docs/agent_prompt.md`, `docs/errors.md`)
- [x] D.7 — Benchmark de tokens (`benchmarks/token_efficiency.py`)
- [x] D.8 — Benchmark de corrección (`benchmarks/correctness.py`)
- [x] D.9 — Instalador Windows (`installer/windows/build.py`)
- [x] D.10 — Instalador Linux (`installer/linux/Makefile`)
- [x] D.11 — CI/CD pipeline (`.github/workflows/ci.yml`, `.github/workflows/release.yml`)
- [x] D.12 — End-to-end test suite (`tests/e2e/test_end_to_end.py`)

## Completado

### D.1 — Programas de ejemplo
- 15 archivos `.lumen` en `examples/` cubriendo todos los modos (fast/safe/flow)
- `examples/README.md` con descripción detallada y tests negativos de cada ejemplo

### D.2 — Test fixtures
- **Lexer** (`tests/compiler/fixtures/lexer/`): 50 fixtures (35 válidos, 15 inválidos)
- **Parser** (`tests/compiler/fixtures/parser/`): 50 fixtures (30 válidos, 20 inválidos)
- **Typecheck** (`tests/compiler/fixtures/typecheck/`): 30 fixtures (24 válidos, 6 inválidos)

### D.3 — Formatter
- `format_source(source) → str` idempotente, 2 espacios, dobles comillas, pipelines con `|`
- `check_format(source) → bool`

### D.4 — Explain mode
- Usa compilador real si disponible; extrae info del AST (capabilities, actions, agents, reversible ops)
- Fallback a regex si compilación falla

### D.5 — Dry-run mode
- Usa compilador real si disponible; genera pasos desde ActionDecl y CapabilityCall en AST
- Fallback a regex si compilación falla

### D.6 — Documentación
- `docs/manual.md`: Manual completo (15 secciones, gramática EBNF, catálogo de capacidades)
- `docs/patterns.md`: 30 patrones canónicos con código completo
- `docs/pitfalls.md`: 20 errores comunes con código incorrecto/correcto
- `docs/agent_prompt.md`: System prompt para LLMs generando código Lumen
- `docs/errors.md`: Catálogo completo LMN-0001 a LMN-0100

### D.7 — Token benchmark
- `benchmarks/token_efficiency.py`: Compara tokens Lumen vs Python (5 programas)

### D.8 — Correctness benchmark
- `benchmarks/correctness.py`: Escanea `examples/*.lumen` y verifica compilación OK

### D.9 — Instalador Windows
- `installer/windows/build.py`: PyInstaller → `lumen.exe`

### D.10 — Instalador Linux
- `installer/linux/Makefile`: ELF + paquete `.deb`

### D.11 — CI/CD
- `ci.yml`: Test en windows-latest + ubuntu-latest para Python 3.11 y 3.12
- `release.yml`: Genera binarios en tags `v*`

### D.12 — End-to-end test suite
- `tests/e2e/test_end_to_end.py`: 9 tests que corren pipeline completo sobre 15 ejemplos

## Bloqueos
(ninguno — todos los tracks completos)
