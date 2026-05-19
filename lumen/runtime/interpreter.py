"""Intérprete Lumen: ejecuta CompiledProgram directamente sobre el AST."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from lumen.runtime.audit import AuditEvent, AuditEventType, AuditLog, AuditMode
from lumen.stdlib.base import ExecutionContext, Result


@dataclass
class ExecutionResult:
    success: bool
    output: Any = None
    error: str = ""
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    mode: str = "fast"


class LumenRuntimeError(Exception):
    """Error en tiempo de ejecución del intérprete Lumen."""

    def __init__(self, message: str, code: str = "LMN-0099") -> None:
        super().__init__(message)
        self.code = code


class Interpreter:
    """Intérprete del AST de Lumen. Async-first."""

    def __init__(
        self,
        context: ExecutionContext | None = None,
        audit_log: AuditLog | None = None,
    ) -> None:
        self._context = context or ExecutionContext()
        self._audit_log = audit_log
        self._env: dict[str, Any] = {}
        self._capabilities: dict[str, Any] = {}
        self._output: list[str] = []

    async def run(self, compiled_program: Any) -> ExecutionResult:
        """Ejecuta un CompiledProgram. Retorna ExecutionResult."""
        if compiled_program is None:
            return ExecutionResult(
                success=False, error="CompiledProgram es None"
            )

        try:
            mode_str = str(getattr(compiled_program, "mode", "fast"))
            self._context.mode = mode_str  # type: ignore[assignment]

            ast = self._get_ast(compiled_program)
            if ast is None:
                return ExecutionResult(
                    success=False,
                    error="No se pudo obtener AST del CompiledProgram",
                )

            await self._exec_program(ast)

            return ExecutionResult(
                success=True,
                output="\n".join(self._output),
                mode=mode_str,
            )
        except LumenRuntimeError as e:
            return ExecutionResult(success=False, error=f"[{e.code}] {e}")
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    @staticmethod
    def _get_ast(compiled_program: Any) -> Any:
        if hasattr(compiled_program, "instrumented"):
            if hasattr(compiled_program.instrumented, "resolved"):
                if hasattr(compiled_program.instrumented.resolved, "typed"):
                    if hasattr(compiled_program.instrumented.resolved.typed, "ast"):
                        return compiled_program.instrumented.resolved.typed.ast
        if hasattr(compiled_program, "ast"):
            return compiled_program.ast
        return None

    async def _exec_program(self, ast: Any) -> None:
        # Program node uses .top_levels; other AST nodes may use .statements or .body
        statements = (
            getattr(ast, "top_levels", None)
            or getattr(ast, "statements", None)
            or getattr(ast, "body", None)
            or []
        )
        for stmt in statements:
            await self._exec_statement(stmt)

    async def _exec_statement(self, stmt: Any) -> Any:
        node_type = type(stmt).__name__

        if node_type == "Assignment":
            value = await self._eval_expr(getattr(stmt, "value", None))
            # ast_nodes.Assignment uses .target (str), not .name
            target = getattr(stmt, "target", None) or getattr(stmt, "name", None)
            if target:
                identifier = getattr(target, "name", str(target))
                self._env[identifier] = value
            return value

        if node_type == "IfStatement":
            return await self._exec_if(stmt)

        if node_type == "ForStatement":
            return await self._exec_for(stmt)

        if node_type == "MatchStatement":
            return await self._exec_match(stmt)

        if node_type == "ReturnStatement":
            value = await self._eval_expr(getattr(stmt, "value", None))
            raise _ReturnValue(value)

        if node_type == "Pipeline":
            return await self._exec_pipeline(stmt)

        if node_type == "ExpressionStatement":
            return await self._eval_expr(getattr(stmt, "expression", None))

        if node_type in ("FunctionCall", "CapabilityCall"):
            return await self._eval_call(stmt)

        if node_type == "PrintStatement":
            value = await self._eval_expr(getattr(stmt, "value", None))
            self._output.append(str(value) if value is not None else "")
            return None

        if node_type == "UndoStatement":
            action_id = await self._eval_expr(getattr(stmt, "action_id", None))
            undo_mgr = getattr(self._context, "undo_manager", None)
            if undo_mgr:
                return undo_mgr.undo(str(action_id))
            return None

        if node_type == "AuditLogCall":
            if self._audit_log:
                from lumen.runtime.audit import AuditEvent, AuditEventType, AuditMode
                import datetime
                event = AuditEvent(
                    event=AuditEventType.EXECUTION,
                    mode=AuditMode(getattr(self._context, "mode", "fast")),
                    action_id=getattr(stmt, "action_name", ""),
                    program=getattr(self._context, "program_path", ""),
                    program_hash=getattr(self._context, "program_hash", ""),
                    details={"level": getattr(stmt, "level", "minimal")},
                    confidence=1.0,
                    reversible=False,
                    human_approved=False,
                    ts=datetime.datetime.utcnow().isoformat(),
                )
                import asyncio
                asyncio.create_task(self._audit_log.record(event))
            return None

        if node_type == "ActionDecl":
            name = getattr(stmt, "name", None)
            if name:
                self._env[str(name)] = stmt
            return None

        if node_type == "FunctionDecl":
            name = getattr(stmt, "name", None)
            if name:
                self._env[str(name)] = stmt
            return None

        return await self._eval_expr(stmt)

    async def _eval_expr(self, expr: Any) -> Any:
        if expr is None:
            return None

        node_type = type(expr).__name__

        if node_type == "NumberLiteral":
            return float(getattr(expr, "value", 0))

        if node_type == "StringLiteral":
            return str(getattr(expr, "value", ""))

        if node_type == "StringInterpolation":
            return await self._eval_string_interp(expr)

        if node_type == "BooleanLiteral":
            return bool(getattr(expr, "value", False))

        if node_type == "MoneyLiteral":
            return {
                "amount": float(getattr(expr, "amount", 0)),
                "currency": str(getattr(expr, "currency", "USD")),
                "__type": "Money",
            }

        if node_type == "TimeLiteral":
            return {
                "value": float(getattr(expr, "value", 0)),
                "unit": str(getattr(expr, "unit", "s")),
                "__type": "Time",
            }

        if node_type == "Identifier":
            name = str(getattr(expr, "name", ""))
            if name in self._env:
                return self._env[name]
            return None

        if node_type == "BinaryOp":
            return await self._eval_binary(expr)

        if node_type in ("FunctionCall", "CapabilityCall"):
            return await self._eval_call(expr)

        if node_type == "Pipeline":
            return await self._exec_pipeline(expr)

        if node_type == "ResolveBlock":
            return await self._eval_resolve(expr)

        if node_type == "PrintStatement":
            value = await self._eval_expr(getattr(expr, "value", None))
            self._output.append(str(value))
            return None

        return str(expr)

    async def _eval_string_interp(self, expr: Any) -> str:
        parts = getattr(expr, "parts", [])
        result = ""
        for part in parts:
            if isinstance(part, str):
                result += part
            else:
                val = await self._eval_expr(part)
                result += str(val) if val is not None else ""
        return result

    async def _eval_binary(self, expr: Any) -> Any:
        left = await self._eval_expr(getattr(expr, "left", None))
        right = await self._eval_expr(getattr(expr, "right", None))
        op = str(getattr(expr, "op", "+"))

        ops: dict[str, Any] = {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b if b != 0 else 0,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }
        fn = ops.get(op)
        if fn and left is not None and right is not None:
            try:
                return fn(left, right)
            except (TypeError, ValueError):
                return None
        return None

    async def _eval_call(self, expr: Any) -> Any:
        # CapabilityCall uses .path tuple; FunctionCall uses .name str
        path = getattr(expr, "path", None)
        if path is not None:
            name = ".".join(str(p) for p in path)
        else:
            name = str(getattr(expr, "name", getattr(expr, "function", "")))

        if name == "print":
            args = getattr(expr, "args", [])
            for arg in args:
                val = await self._eval_expr(arg)
                self._output.append(str(val) if val is not None else "")
            return None

        if name in self._env:
            fn = self._env[name]
            if hasattr(fn, "execute"):
                args_list = getattr(expr, "args", [])
                args_dict = {}
                for i, arg in enumerate(args_list):
                    val = await self._eval_expr(arg)
                    args_dict[str(i)] = val
                result = await fn.execute(args_dict, self._context)
                return result.value if isinstance(result, Result) else result

        capability = self._capabilities.get(name)
        if capability is not None:
            args_list = getattr(expr, "args", [])
            cap_args_dict: dict[str, Any] = {}
            args_dict = cap_args_dict
            for i, arg in enumerate(args_list):
                val = await self._eval_expr(arg)
                args_dict[str(i)] = val
            # merge kwargs (k=v pairs from CapabilityCall/FunctionCall)
            for k, v_expr in getattr(expr, "kwargs", ()):
                args_dict[str(k)] = await self._eval_expr(v_expr)
            result = await capability.execute(args_dict, self._context)
            return result.value if isinstance(result, Result) else result

        return f"[{name}(...)]"

    async def _exec_if(self, stmt: Any) -> Any:
        condition = await self._eval_expr(getattr(stmt, "condition", None))
        if condition:
            return await self._exec_block(getattr(stmt, "then_block", None))
        else:
            else_block = getattr(stmt, "else_block", None)
            if else_block:
                return await self._exec_block(else_block)
        return None

    async def _exec_for(self, stmt: Any) -> None:
        # ast_nodes.ForStatement uses .target (str) and .body (Block)
        var = str(getattr(stmt, "target", None) or getattr(stmt, "variable", "item"))
        iterable = await self._eval_expr(getattr(stmt, "iterable", None))
        block = getattr(stmt, "body", None) or getattr(stmt, "block", None)

        if not hasattr(iterable, "__iter__"):
            return

        for item in iterable:
            self._env[var] = item
            try:
                await self._exec_block(block)
            except _ReturnValue:
                break

    async def _exec_match(self, stmt: Any) -> Any:
        # ast_nodes.MatchStatement uses .subject, not .value
        value = await self._eval_expr(getattr(stmt, "subject", None) or getattr(stmt, "value", None))
        arms = getattr(stmt, "arms", [])

        for arm in arms:
            pattern = getattr(arm, "pattern", None)
            if await self._match_pattern(value, pattern):
                return await self._exec_block(getattr(arm, "block", None))
        return None

    async def _match_pattern(self, value: Any, pattern: Any) -> bool:
        if pattern is None:
            return True
        pattern_str = str(getattr(pattern, "name", str(pattern)))
        if pattern_str in ("ok", "_", "default"):
            return True
        if pattern_str == "fail" and isinstance(value, dict) and not value.get("success", True):
            return True
        return False

    async def _exec_block(self, block: Any) -> Any:
        if block is None:
            return None
        statements = getattr(block, "statements", []) or []
        result = None
        for stmt in statements:
            try:
                result = await self._exec_statement(stmt)
            except _ReturnValue as rv:
                return rv.value
        return result

    async def _exec_pipeline(self, pipeline: Any) -> Any:
        steps = getattr(pipeline, "steps", []) or getattr(pipeline, "expressions", [])
        value: Any = None

        for i, step in enumerate(steps):
            if i == 0:
                value = await self._eval_expr(step)
            else:
                if hasattr(step, "args"):
                    existing_args = list(getattr(step, "args", []))
                    value = await self._apply_fn(step, value)
                else:
                    value = await self._apply_fn(step, value)

        return value

    async def _apply_fn(self, fn_expr: Any, input_value: Any) -> Any:
        name = str(getattr(fn_expr, "name", getattr(fn_expr, "function", "")))

        if name == "filter":
            args = getattr(fn_expr, "args", [])
            predicate = args[0] if args else None
            if hasattr(input_value, "__iter__") and predicate is not None:
                results = []
                for item in input_value:
                    self._env["_item"] = item
                    if await self._eval_expr(predicate):
                        results.append(item)
                return results
            return input_value

        if name in ("take", "limit"):
            args = getattr(fn_expr, "args", [])
            n = int(await self._eval_expr(args[0])) if args else 10
            if hasattr(input_value, "__iter__"):
                return list(input_value)[:n]
            return input_value

        if name == "sort_by":
            if hasattr(input_value, "__iter__"):
                return sorted(input_value, key=lambda x: x if isinstance(x, (int, float)) else 0)
            return input_value

        return await self._eval_call(fn_expr)

    async def _eval_resolve(self, resolve_block: Any) -> Any:
        # ast_nodes.ResolveBlock uses .subject, not .expression
        ambiguous = await self._eval_expr(
            getattr(resolve_block, "subject", None) or getattr(resolve_block, "expression", None)
        )
        strategies = getattr(resolve_block, "strategies", [])

        if self._context.dry_run:
            return f"[PENDING: resolve({ambiguous!r})]"

        llm_client = getattr(self._context, "llm_client", None)
        if llm_client is not None:
            strategy_names = [str(getattr(s, "name", "")) for s in strategies]
            resolution = await llm_client.resolve(
                str(ambiguous), {}, strategy_names
            )
            return resolution.value

        for strategy in strategies:
            strategy_name = str(getattr(strategy, "name", ""))
            if strategy_name == "fail_safe":
                raise LumenRuntimeError(
                    f"No se pudo resolver: {ambiguous!r}", code="LMN-0002"
                )

        return ambiguous

    def register_capability(self, name: str, capability: Any) -> None:
        self._capabilities[name] = capability

    def set_env(self, name: str, value: Any) -> None:
        self._env[name] = value


class _ReturnValue(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value
