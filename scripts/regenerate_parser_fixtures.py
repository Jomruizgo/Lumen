"""Regenera los archivos .expected del parser de los fixtures existentes.

Uso:
    py scripts/regenerate_parser_fixtures.py [--dry-run]

Por cada fixture .lumen, corre el parser y escribe el JSON resultante en .expected.
Preserva los fixtures "invalid" (donde se espera ParseError) — solo regenera los "valid".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Añadir el directorio raíz al path para importar lumen
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from lumen.compiler.parser import ParseError, parse  # noqa: E402

FIXTURES_DIR = ROOT / "tests" / "compiler" / "fixtures" / "parser"


# Mismo mapa de nombres que usa test_parser.py para comparación
_NODE_TYPE_MAP: dict[str, str] = {
    "Program": "Program",
    "ExpressionStatement": "ExprStatement",
    "FunctionCall": "Call",
    "StringLiteral": "StringLiteral",
    "NumberLiteral": "NumberLiteral",
    "BooleanLiteral": "BooleanLiteral",
    "TimeLiteral": "TimeLiteral",
    "MoneyLiteral": "MoneyLiteral",
    "Identifier": "Identifier",
    "BinaryOp": "BinaryOp",
    "UnaryOp": "UnaryOp",
    "FunctionDecl": "FunctionDecl",
    "ActionDecl": "ActionDecl",
    "AgentDecl": "AgentDecl",
    "CapabilityDecl": "CapabilityDecl",
    "ImportDecl": "ImportDecl",
    "Assignment": "Assignment",
    "ReturnStatement": "ReturnStatement",
    "Pipeline": "Pipeline",
    "ResolveBlock": "ResolveBlock",
    "IfStatement": "IfStatement",
    "MatchStatement": "MatchStatement",
    "ForStatement": "ForStatement",
    "PrintStatement": "ExprStatement",
    "Block": "Block",
    "MatchArm": "MatchArm",
    "Param": "Param",
    "OnClause": "OnHandler",
    "WatchClause": "WatchClause",
    "StateClause": "StateClause",
    "ConfigClause": "ConfigClause",
    "StringInterpolation": "StringInterp",
    "DotAccess": "DotAccess",
    "IndexAccess": "IndexAccess",
    "ActionBody": "ActionBody",
    "AgentBody": "AgentBody",
    "ModeClause": "ModeClause",
    "RequiresClause": "RequiresClause",
    "ReversibleClause": "ReversibleClause",
    "AuditClause": "AuditClause",
    "EscalationClause": "EscalationClause",
    "ExecuteClause": "ExecuteClause",
    "StrategyClause": "StrategyClause",
    "PassStatement": "PassStatement",
    "UndoStatement": "UndoStatement",
    "PrimitiveType": "PrimitiveType",
    "ParametrizedType": "ParametrizedType",
    "UnionType": "UnionType",
    "BecauseAnnotation": "BecauseAnnotation",
    "AuditLogCall": "AuditLogCall",
    "VersionDecl": "VersionDecl",
}


def _node_to_dict(node: object) -> object:
    """Serializa un nodo AST a dict simple usando los mismos nombres que test_parser.py."""
    if node is None:
        return None
    if isinstance(node, (bool, int, float, str)):
        return node
    if isinstance(node, (list, tuple)):
        return [_node_to_dict(item) for item in node]

    # Para pydantic models
    node_cls = type(node)
    if hasattr(node_cls, "model_fields"):
        cls_name = node_cls.__name__
        mapped = _NODE_TYPE_MAP.get(cls_name, cls_name)
        d: dict[str, object] = {"node_type": mapped}
        for field_name in node_cls.model_fields:
            val = getattr(node, field_name, None)
            if val is None:
                continue
            if field_name == "position":
                continue
            d[field_name] = _node_to_dict(val)
        return d

    return str(node)


def regenerate(dry_run: bool = False, include_warn: bool = False) -> None:
    if not FIXTURES_DIR.exists():
        print(f"[ERROR] Directorio no existe: {FIXTURES_DIR}")
        sys.exit(1)

    lumen_files = sorted(FIXTURES_DIR.glob("*.lumen"))
    updated = 0
    skipped_invalid = 0
    errors = 0

    for lumen_path in lumen_files:
        expected_path = lumen_path.with_suffix(".expected")

        source = lumen_path.read_text(encoding="utf-8")

        # Determinar si el fixture actual espera error
        is_invalid = False
        if expected_path.exists():
            try:
                existing = json.loads(expected_path.read_text(encoding="utf-8"))
                is_invalid = existing.get("valid") is False
            except json.JSONDecodeError:
                pass

        result = parse(source)

        if is_invalid:
            if not isinstance(result, ParseError):
                if include_warn:
                    pass  # fall through to regenerate below
                else:
                    print(f"[WARN] {lumen_path.name}: era invalido, ahora parsea. Usar --include-warn para actualizar.")
                    skipped_invalid += 1
                    continue
            else:
                print(f"[SKIP] {lumen_path.name}: invalido (ParseError) -- sin cambios")
                skipped_invalid += 1
                continue

        if isinstance(result, ParseError):
            print(f"[ERROR] {lumen_path.name}: ParseError inesperado: {result.message} L{result.line}:{result.col}")
            errors += 1
            continue

        # Serializar resultado
        output = _node_to_dict(result)
        if isinstance(output, dict):
            output["valid"] = True

        json_str = json.dumps(output, ensure_ascii=False, indent=2)

        if dry_run:
            print(f"[DRY-RUN] {lumen_path.name} -> {expected_path.name}")
            print(json_str[:200] + ("..." if len(json_str) > 200 else ""))
            print()
        else:
            expected_path.write_text(json_str + "\n", encoding="utf-8")
            print(f"[OK] {lumen_path.name} -> regenerado")
            updated += 1

    print()
    if dry_run:
        print(f"DRY-RUN: {len(lumen_files)} fixtures procesados, {skipped_invalid} inválidos, {errors} errores")
    else:
        print(f"Regenerados: {updated}, inválidos preservados: {skipped_invalid}, errores: {errors}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    warn = "--include-warn" in sys.argv
    regenerate(dry_run=dry, include_warn=warn)
