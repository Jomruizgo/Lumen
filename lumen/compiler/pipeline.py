"""Pass A.11 — Compiler Pipeline.

Orquesta todos los passes del compilador Lumen en orden y retorna un
CompileResult con el programa compilado o la lista de errores acumulados.

Orden de passes:
  1. parse           → Program | ParseError
  2. detect_mode     → ModeResult | CompileError
  3. check_caps      → list[CompileError]
  4. typecheck       → TypedProgram | list[CompileError]
  5. resolve         → ResolvedProgram | list[CompileError]
  6. check_rev       → list[CompileError]
  7. inject_audit    → InstrumentedProgram

Si parse falla → parada inmediata (no hay AST).
El resto de passes se intenta ejecutar aunque haya errores previos, para
reportar tantos errores como sea posible en una sola pasada.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from lumen.compiler.parser import parse, ParseError
from lumen.compiler.rev_checker import check_reversibility
from lumen.compiler.audit_injector import inject_audit, InstrumentedProgram

# ---------------------------------------------------------------------------
# Imports con tolerancia a módulos aún no implementados.
# Los passes en paralelo (mode_detector, cap_checker, typechecker, resolver)
# se importan con fallbacks para que el pipeline sea arrancable aunque alguno
# falte durante el desarrollo.
# ---------------------------------------------------------------------------

def _import_mode_detector() -> Any:
    try:
        from lumen.compiler.mode_detector import detect_mode, ModeResult
        return detect_mode, ModeResult
    except ImportError:
        return None, None


def _import_cap_checker() -> Any:
    try:
        from lumen.compiler.cap_checker import check_capabilities
        return check_capabilities
    except ImportError:
        return None


def _import_typechecker() -> Any:
    try:
        from lumen.compiler.typechecker import typecheck, TypedProgram
        return typecheck, TypedProgram
    except ImportError:
        return None, None


def _import_resolver() -> Any:
    try:
        from lumen.compiler.resolver import resolve_semantics, ResolvedProgram
        return resolve_semantics, ResolvedProgram
    except ImportError:
        return None, None


# ---------------------------------------------------------------------------
# Tipos de datos del pipeline
# ---------------------------------------------------------------------------

@dataclass
class CompileError:
    """Error de compilación con código, mensaje y posición."""
    code: str       # "LMN-XXXX"
    message: str
    line: int
    col: int


@dataclass
class CompiledProgram:
    """Resultado exitoso de la compilación."""
    source: str
    source_hash: str                         # "sha256:" + hexdigest
    mode: Literal["fast", "safe", "flow"]
    instrumented: InstrumentedProgram
    # Acceso para el intérprete:
    #   compiled_program.instrumented.resolved.typed.ast  → Program
    #   compiled_program.mode                             → str


@dataclass
class CompileResult:
    """Resultado de una compilación: ok + program, o lista de errores."""
    ok: bool
    program: Optional[CompiledProgram] = None
    errors: list[CompileError] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Adaptadores de errores de passes externos
# ---------------------------------------------------------------------------

def _adapt_error(err: Any) -> CompileError:
    """Convierte un error de cualquier formato a CompileError."""
    if isinstance(err, CompileError):
        return err

    # rev_checker.CompileError (misma estructura, distinto módulo)
    code = getattr(err, "code", "LMN-0000")
    message = getattr(err, "message", str(err))
    line = getattr(err, "line", 0)
    col = getattr(err, "col", 0)
    return CompileError(code=code, message=message, line=line, col=col)


def _adapt_errors(errs: list[Any]) -> list[CompileError]:
    return [_adapt_error(e) for e in errs]


def _parse_error_to_compile_error(pe: ParseError) -> CompileError:
    return CompileError(
        code=getattr(pe, "code", "LMN-0010"),
        message=pe.message,
        line=pe.line,
        col=pe.col,
    )


# ---------------------------------------------------------------------------
# Stub de TypedProgram / ResolvedProgram cuando los passes no están disponibles
# ---------------------------------------------------------------------------

class _StubTyped:
    """TypedProgram mínimo para cuando typechecker no está disponible."""
    def __init__(self, ast: Any) -> None:
        self.ast = ast


class _StubResolved:
    """ResolvedProgram mínimo para cuando resolver no está disponible."""
    def __init__(self, typed: Any) -> None:
        self.typed = typed


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

class CompilerPipeline:
    """Orquestador de todos los passes del compilador Lumen."""

    def compile(self, source: str) -> CompileResult:
        """Ejecuta todos los passes y retorna CompileResult.

        Si algún pass produce errores se continúa con los siguientes donde sea
        posible, para acumular todos los diagnósticos en una sola pasada. Solo
        se detiene tempranamente si el parser falla (no hay AST disponible).
        """
        all_errors: list[CompileError] = []

        # ------------------------------------------------------------------ #
        # 1. Parse
        # ------------------------------------------------------------------ #
        parse_result = parse(source)
        if isinstance(parse_result, ParseError):
            return CompileResult(
                ok=False,
                errors=[_parse_error_to_compile_error(parse_result)],
            )

        program = parse_result

        # ------------------------------------------------------------------ #
        # 2. Mode detection
        # ------------------------------------------------------------------ #
        detect_mode, _ModeResult = _import_mode_detector()
        mode: str = "fast"  # valor por defecto seguro
        mode_ok = True

        if detect_mode is not None:
            mode_result = detect_mode(program)
            # ModeResult o CompileError
            if _is_error_like(mode_result):
                all_errors.append(_adapt_error(mode_result))
                mode_ok = False
            else:
                # ModeResult: acceder a .mode
                mode = getattr(mode_result, "mode", "fast")

        # ------------------------------------------------------------------ #
        # 3. Capability check
        # ------------------------------------------------------------------ #
        check_capabilities = _import_cap_checker()
        if check_capabilities is not None:
            cap_errors = check_capabilities(program)
            if cap_errors:
                all_errors.extend(_adapt_errors(cap_errors))

        # ------------------------------------------------------------------ #
        # 4. Typechecker
        # ------------------------------------------------------------------ #
        typecheck, _TypedProgram = _import_typechecker()
        typed: Any = _StubTyped(program)
        typed_ok = True

        if typecheck is not None:
            typed_result = typecheck(program, mode)
            if isinstance(typed_result, list):
                # list[CompileError]
                all_errors.extend(_adapt_errors(typed_result))
                typed_ok = False
            else:
                typed = typed_result

        # ------------------------------------------------------------------ #
        # 5. Resolver
        # ------------------------------------------------------------------ #
        resolve_semantics, _ResolvedProgram = _import_resolver()
        resolved: Any = _StubResolved(typed)
        resolved_ok = True

        if resolve_semantics is not None and typed_ok:
            resolved_result = resolve_semantics(typed, mode)
            if isinstance(resolved_result, list):
                all_errors.extend(_adapt_errors(resolved_result))
                resolved_ok = False
            else:
                resolved = resolved_result
        elif resolve_semantics is not None and not typed_ok:
            # typed falló — construir un resolved stub con lo que tenemos
            resolved = _StubResolved(typed)

        # ------------------------------------------------------------------ #
        # 6. Reversibility check
        # ------------------------------------------------------------------ #
        rev_errors = check_reversibility(program)
        if rev_errors:
            all_errors.extend(_adapt_errors(rev_errors))

        # ------------------------------------------------------------------ #
        # 7. Audit injection (solo si no hay errores bloqueantes anteriores)
        # ------------------------------------------------------------------ #
        if all_errors:
            return CompileResult(ok=False, errors=all_errors)

        instrumented = inject_audit(resolved, mode)

        # ------------------------------------------------------------------ #
        # Resultado final
        # ------------------------------------------------------------------ #
        source_hash = "sha256:" + hashlib.sha256(source.encode()).hexdigest()
        compiled = CompiledProgram(
            source=source,
            source_hash=source_hash,
            mode=mode,  # type: ignore[arg-type]
            instrumented=instrumented,
        )
        return CompileResult(ok=True, program=compiled)

    def check(self, source: str) -> list[CompileError]:
        """Ejecuta los passes de validación sin producir salida.

        Útil para herramientas de linting / LSP.
        """
        result = self.compile(source)
        if result.ok:
            return []
        return result.errors


# ---------------------------------------------------------------------------
# Función de conveniencia a nivel de módulo
# ---------------------------------------------------------------------------

def compile_source(source: str) -> CompileResult:
    """Compila source usando una instancia fresca de CompilerPipeline."""
    return CompilerPipeline().compile(source)


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _is_error_like(obj: Any) -> bool:
    """Heurística: el objeto es un error si tiene atributo 'code' y 'message'."""
    return hasattr(obj, "code") and hasattr(obj, "message") and hasattr(obj, "line")
