# Lumen — Especificación Técnica

> Lenguaje de programación con dos modos (fast / safe) y orquestación (flow), diseñado para que LLMs generen código eficiente cuando no importa, y código auditable cuando importa.

---

## Cómo usar esta especificación

Esta especificación está diseñada para ser ejecutada por **Claude Code en paralelo**. Cuatro instancias pueden trabajar simultáneamente, una por track.

### Archivos

| Archivo | Contenido | Cuándo leerlo |
|---|---|---|
| `README.md` | Este archivo. Guía maestra. | Primero |
| `SPEC.md` | Especificación formal del lenguaje | Todos los agentes |
| `ARCHITECTURE.md` | ADRs, stack, decisiones tomadas | Todos los agentes |
| `TASKS.md` | Tareas atómicas por track | Por track asignado |
| `EXAMPLES.md` | Programas canónicos (casos de prueba) | Para validación |

---

## Decisiones ya tomadas (NO se renegocian)

| # | Decisión |
|---|---|
| 1 | Nombre del lenguaje: **Lumen** |
| 2 | Extensión de archivos: **`.lumen`** |
| 3 | Implementación inicial: **Python 3.11+** (rewrite a Rust planeado v2) |
| 4 | OS target v1: **Windows 10+** (Linux soportado, macOS post-v1) |
| 5 | Canal de escalación: **CLI interactivo + webhook HTTP** |
| 6 | Stdlib v1: **Completa** (comm, time, data, sensitive, cli, web) |
| 7 | Distribución: **Binario único (PyInstaller) + package managers** (winget, apt) |
| 8 | Modos del lenguaje: **fast / safe / flow** |

---

## Tracks paralelizables

```
Track A: Compiler  ──┐
                     ├── pueden empezar inmediatamente
Track D: Examples ───┘   (independientes entre sí)

Track B: Runtime    ── empieza cuando A1 (AST) está completo
Track C: Stdlib     ── empieza cuando B1 (motor base) está completo
```

### Track A — Compiler
Lexer, parser, AST, type checker, resolver semántico.
Asignar a una instancia de Claude Code dedicada.

### Track B — Runtime
Intérprete, sandbox, sistema de auditoría, undo.
Depende de A1 (AST definido). Puede empezar a las 2 semanas.

### Track C — Stdlib
Capacidades nativas: comm, time, data, sensitive, cli, web.
Depende de B1 (motor base ejecutando). Puede empezar a las 4 semanas.

### Track D — Tooling, Tests, Docs
Programas de ejemplo, fixtures de test, formatter, explain, dry-run, docs.
Puede empezar inmediatamente con SPEC.md.

---

## Cómo asignar trabajo a Claude Code

Para cada track, abrir una sesión de Claude Code con este prompt inicial:

```
Vas a trabajar en el Track [X] del lenguaje Lumen.

Lee en este orden:
1. /lumen-spec/README.md
2. /lumen-spec/ARCHITECTURE.md
3. /lumen-spec/SPEC.md
4. /lumen-spec/TASKS.md (sección Track [X])
5. /lumen-spec/EXAMPLES.md

Reglas:
- Implementa las tareas en el orden listado
- Cada tarea tiene un criterio de aceptación ejecutable. No pases a la siguiente sin que pase.
- No tomes decisiones no documentadas. Si encuentras ambigüedad, detente y pregunta.
- Todo el código en Python 3.11+ con type hints estrictos.
- Tests con pytest. Cobertura mínima por tarea: 80%.

Empieza con la tarea [X.1].
```

---

## Estructura final del proyecto

Al terminar, el repositorio se verá así:

```
lumen/
├── lumen/                    # Código del compilador y runtime
│   ├── compiler/
│   │   ├── lexer.py
│   │   ├── parser.py
│   │   ├── ast_nodes.py
│   │   ├── typecheck.py
│   │   └── resolver.py
│   ├── runtime/
│   │   ├── interpreter.py
│   │   ├── sandbox.py
│   │   ├── audit.py
│   │   └── undo.py
│   ├── stdlib/
│   │   ├── comm/
│   │   ├── time/
│   │   ├── data/
│   │   ├── sensitive/
│   │   ├── cli/
│   │   └── web/
│   └── tooling/
│       ├── format.py
│       ├── explain.py
│       └── dryrun.py
├── tests/
│   ├── compiler/
│   ├── runtime/
│   ├── stdlib/
│   ├── e2e/
│   └── benchmarks/
├── examples/                 # Programas .lumen de ejemplo
├── docs/
│   ├── manual.md
│   ├── patterns.md
│   └── agent_prompt.md
├── installer/
│   ├── windows/             # PyInstaller spec para .exe
│   └── linux/               # Paquete .deb
├── pyproject.toml
└── README.md
```

---

## Definition of Done global

El lenguaje está completo cuando estos comandos pasan:

```bash
# 1. Todos los tests unitarios pasan
pytest tests/ --cov=lumen --cov-fail-under=80

# 2. Todos los programas de EXAMPLES.md ejecutan correctamente
lumen run examples/canonical/*.lumen --check-only

# 3. Benchmark de tokens: Lumen usa ≤50% que Python para tareas equivalentes
python tests/benchmarks/token_efficiency.py --threshold=0.5

# 4. Benchmark de corrección: ≥90% al primer intento en suite de prompts
python tests/benchmarks/correctness.py --threshold=0.9

# 5. Instalador Windows compila y ejecuta
cd installer/windows && python build.py && ./dist/lumen.exe --version

# 6. Instalador Linux compila y ejecuta
cd installer/linux && make && ./build/lumen --version
```

Si los 6 comandos retornan exit code 0, el lenguaje está terminado.

---

## Siguiente paso

Lee `ARCHITECTURE.md` para las decisiones técnicas, luego `SPEC.md` para el lenguaje, finalmente `TASKS.md` para tu track asignado.
