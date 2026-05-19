"""Compilador Lumen: lexer, parser, AST, type checker, resolver."""

from lumen.compiler.pipeline import CompileResult, CompilerPipeline, compile_source
from lumen.compiler.parser import ParseError, parse
from lumen.compiler.mode_detector import ModeResult, detect_mode
from lumen.compiler.cap_checker import check_capabilities
from lumen.compiler.typechecker import TypedProgram, typecheck
from lumen.compiler.resolver import ResolvedProgram, resolve_semantics
from lumen.compiler.rev_checker import check_reversibility
from lumen.compiler.audit_injector import InstrumentedProgram, inject_audit

__all__ = [
    "CompileResult",
    "CompilerPipeline",
    "compile_source",
    "ParseError",
    "parse",
    "ModeResult",
    "detect_mode",
    "check_capabilities",
    "TypedProgram",
    "typecheck",
    "ResolvedProgram",
    "resolve_semantics",
    "check_reversibility",
    "InstrumentedProgram",
    "inject_audit",
]
