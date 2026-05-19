"""Parser de Lumen.

Convierte source string → AST (Program).
Usa el lexer interno de Lumen + parser recursivo descendente.

Errores: LMN-0010 (SyntaxError), LMN-0100 (MissingVersionDeclaration).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from lumen.compiler.ast_nodes import (
    ActionBody,
    ActionDecl,
    AgentBody,
    AgentDecl,
    Assignment,
    AuditClause,
    BecauseAnnotation,
    BinaryOp,
    Block,
    BooleanLiteral,
    CapabilityDecl,
    ConfigClause,
    DotAccess,
    EscalationClause,
    ExecuteClause,
    ExpressionStatement,
    ForStatement,
    FunctionCall,
    FunctionDecl,
    Identifier,
    IfStatement,
    ImportDecl,
    IndexAccess,
    MatchArm,
    MatchStatement,
    ModeClause,
    MoneyLiteral,
    NumberLiteral,
    OnClause,
    Param,
    ParametrizedType,
    PassStatement,
    Pipeline,
    PrintStatement,
    PrimitiveType,
    Program,
    RequiresClause,
    ResolveBlock,
    ReturnStatement,
    ReversibleClause,
    ScheduleClause,
    SourcePosition,
    StateClause,
    StrategyClause,
    StringInterpolation,
    StringLiteral,
    TimeLiteral,
    UnaryOp,
    UndoStatement,
    UnionType,
    VersionDecl,
    WatchClause,
    Expression,
    Statement,
    Type,
)
from lumen.compiler.lexer import LexError, Token, TokenType, tokenize


@dataclass
class ParseError:
    message: str
    line: int
    col: int
    suggestion: str = ""
    code: str = "LMN-0010"


class Parser:
    """Parser recursivo descendente para Lumen.

    Trabaja directamente con el stream de tokens incluyendo INDENT/DEDENT/NEWLINE.
    """

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0
        self._allow_lambda = False  # True only inside _parse_call_args

    # -----------------------------------------------------------------------
    # Utilidades básicas
    # -----------------------------------------------------------------------

    def _cur(self) -> Optional[Token]:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _peek(self, offset: int = 1) -> Optional[Token]:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return None

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _pos_from(self, tok: Optional[Token]) -> SourcePosition:
        if tok:
            return SourcePosition(line=tok.line, col=tok.col)
        return SourcePosition(line=0, col=0)

    def _at(self, *types: TokenType) -> bool:
        tok = self._cur()
        return tok is not None and tok.type in types

    def _match(self, *types: TokenType) -> Optional[Token]:
        if self._at(*types):
            return self._advance()
        return None

    def _expect(self, ttype: TokenType) -> Union[Token, ParseError]:
        tok = self._cur()
        if tok is None or tok.type != ttype:
            got = tok.type.name if tok else "EOF"
            line = tok.line if tok else 0
            col = tok.col if tok else 0
            return ParseError(
                message=f"Se esperaba {ttype.name}, se obtuvo {got}",
                line=line,
                col=col,
                code="LMN-0010",
            )
        return self._advance()

    def _skip_newlines(self) -> None:
        """Salta tokens NEWLINE."""
        while self._at(TokenType.NEWLINE):
            self._advance()

    def _skip_ws(self) -> None:
        """Salta NEWLINE, INDENT y DEDENT (para expresiones multi-línea)."""
        while self._at(TokenType.NEWLINE) or self._at(TokenType.INDENT) or self._at(TokenType.DEDENT):
            self._advance()

    def _cur_non_newline(self) -> Optional[Token]:
        """Retorna el token actual ignorando NEWLINEs."""
        i = self._pos
        while i < len(self._tokens) and self._tokens[i].type == TokenType.NEWLINE:
            i += 1
        if i < len(self._tokens):
            return self._tokens[i]
        return None

    def _at_content(self, *types: TokenType) -> bool:
        """Verifica si el próximo token no-NEWLINE es de los tipos dados."""
        tok = self._cur_non_newline()
        return tok is not None and tok.type in types

    # -----------------------------------------------------------------------
    # Bloques
    # -----------------------------------------------------------------------

    def _parse_block(self) -> Union[Block, ParseError]:
        """Parsea: NEWLINE+ INDENT stmt+ DEDENT"""
        self._skip_newlines()

        indent = self._match(TokenType.INDENT)
        if indent is None:
            tok = self._cur()
            line = tok.line if tok else 0
            col = tok.col if tok else 0
            return ParseError("Se esperaba bloque indentado (INDENT)", line, col)

        block_pos = self._pos_from(indent)
        statements: list[Statement] = []

        while True:
            self._skip_newlines()
            if self._at(TokenType.DEDENT) or self._at(TokenType.EOF):
                break
            tok = self._cur()
            if tok is None:
                break

            stmt = self._parse_statement()
            if isinstance(stmt, ParseError):
                return stmt
            statements.append(stmt)

        dedent = self._match(TokenType.DEDENT)
        # DEDENT es opcional al final del archivo

        if not statements:
            # Bloque vacío — esto es un error pero toleramos pass
            pass

        return Block(position=block_pos, statements=tuple(statements))

    # -----------------------------------------------------------------------
    # Parse principal
    # -----------------------------------------------------------------------

    def parse(self) -> Union[Program, ParseError]:
        """Punto de entrada."""
        self._skip_newlines()

        tok = self._cur()
        if tok is None or tok.type != TokenType.VERSION:
            line = tok.line if tok else 1
            col = tok.col if tok else 1
            return ParseError(
                message="Se esperaba '@lumen <version>' al inicio del programa",
                line=line,
                col=col,
                code="LMN-0100",
            )

        ver_tok = self._advance()
        pos = self._pos_from(ver_tok)
        parts = ver_tok.value.split()
        ver_parts = parts[1].split(".") if len(parts) >= 2 else ["1", "0"]
        major = int(ver_parts[0])
        minor = int(ver_parts[1]) if len(ver_parts) > 1 else 0
        version = VersionDecl(position=pos, major=major, minor=minor)

        top_levels: list[object] = []

        while True:
            self._skip_newlines()
            tok = self._cur()
            if tok is None or tok.type == TokenType.EOF:
                break

            result = self._parse_top_level()
            if isinstance(result, ParseError):
                return result
            if result is not None:
                top_levels.append(result)

        return Program(
            position=pos,
            version=version,
            top_levels=tuple(top_levels),  # type: ignore[arg-type]
        )

    def _parse_top_level(self) -> Union[object, ParseError, None]:
        tok = self._cur()
        if tok is None:
            return None

        if tok.type == TokenType.DOC_COMMENT:
            self._advance()
            return None

        if tok.type == TokenType.USE:
            return self._parse_capability_decl()

        if tok.type == TokenType.IMPORT:
            return self._parse_import_decl()

        if tok.type == TokenType.AGENT:
            return self._parse_agent_decl()

        if tok.type == TokenType.ACTION:
            return self._parse_action_decl()

        if tok.type == TokenType.FN:
            return self._parse_function_decl()

        return self._parse_statement()

    # -----------------------------------------------------------------------
    # Declaraciones
    # -----------------------------------------------------------------------

    def _parse_capability_decl(self) -> Union[CapabilityDecl, ParseError]:
        use_tok = self._advance()
        pos = self._pos_from(use_tok)

        # Accept any token as a path part (keywords like 'audit', 'state' are valid cap names)
        def _consume_path_part() -> Union[str, ParseError]:
            tok = self._cur()
            if tok is None:
                return ParseError("Se esperaba nombre de capacidad", 0, 0, "LMN-0010")
            self._advance()
            return str(tok.value)

        path_parts: list[str] = []
        first = _consume_path_part()
        if isinstance(first, ParseError):
            return first
        path_parts.append(first)

        while self._at(TokenType.DOT):
            self._advance()
            part = _consume_path_part()
            if isinstance(part, ParseError):
                return part
            path_parts.append(part)

        alias: Optional[str] = None
        if self._at(TokenType.AS):
            self._advance()
            alias_tok = self._expect(TokenType.IDENTIFIER)
            if isinstance(alias_tok, ParseError):
                return alias_tok
            alias = alias_tok.value

        self._skip_newlines()
        return CapabilityDecl(position=pos, path=tuple(path_parts), alias=alias)

    def _parse_import_decl(self) -> Union[ImportDecl, ParseError]:
        import_tok = self._advance()
        pos = self._pos_from(import_tok)

        path = ""
        from_std = False
        alias: Optional[str] = None

        tok = self._cur()
        if tok and tok.type == TokenType.STRING:
            path = tok.value
            self._advance()
        elif tok and tok.type == TokenType.IDENTIFIER:
            path = tok.value
            self._advance()
            if self._at(TokenType.FROM):
                self._advance()
                src_tok = self._expect(TokenType.IDENTIFIER)
                if isinstance(src_tok, ParseError):
                    return src_tok
                from_std = src_tok.value == "std"

        if self._at(TokenType.AS):
            self._advance()
            alias_tok = self._expect(TokenType.IDENTIFIER)
            if isinstance(alias_tok, ParseError):
                return alias_tok
            alias = alias_tok.value

        self._skip_newlines()
        return ImportDecl(position=pos, path=path, alias=alias, from_std=from_std)

    def _parse_function_decl(self) -> Union[FunctionDecl, ParseError]:
        fn_tok = self._advance()
        pos = self._pos_from(fn_tok)

        name_tok = self._expect(TokenType.IDENTIFIER)
        if isinstance(name_tok, ParseError):
            return name_tok

        if isinstance(self._expect(TokenType.LPAREN), ParseError):
            return ParseError("Se esperaba '('", name_tok.line, name_tok.col)

        params = self._parse_params()
        if isinstance(params, ParseError):
            return params

        if isinstance(self._expect(TokenType.RPAREN), ParseError):
            return ParseError("Se esperaba ')'", fn_tok.line, fn_tok.col)

        return_type: Optional[Type] = None
        if self._at(TokenType.ARROW):
            self._advance()
            return_type = self._parse_type()  # type: ignore[assignment]
            if isinstance(return_type, ParseError):
                return return_type

        colon = self._expect(TokenType.COLON)
        if isinstance(colon, ParseError):
            return colon

        body = self._parse_block()
        if isinstance(body, ParseError):
            return body

        return FunctionDecl(
            position=pos,
            name=name_tok.value,
            params=params,
            return_type=return_type,
            body=body,
        )

    def _parse_action_decl(self) -> Union[ActionDecl, ParseError]:
        action_tok = self._advance()
        pos = self._pos_from(action_tok)

        name_tok = self._expect(TokenType.IDENTIFIER)
        if isinstance(name_tok, ParseError):
            return name_tok

        if isinstance(self._expect(TokenType.LPAREN), ParseError):
            return ParseError("Se esperaba '('", name_tok.line, name_tok.col)

        params = self._parse_params()
        if isinstance(params, ParseError):
            return params

        if isinstance(self._expect(TokenType.RPAREN), ParseError):
            return ParseError("Se esperaba ')'", name_tok.line, name_tok.col)

        colon = self._expect(TokenType.COLON)
        if isinstance(colon, ParseError):
            return colon

        body = self._parse_action_body(pos)
        if isinstance(body, ParseError):
            return body

        return ActionDecl(position=pos, name=name_tok.value, params=params, body=body)

    def _parse_action_body(self, decl_pos: SourcePosition) -> Union[ActionBody, ParseError]:
        self._skip_newlines()
        indent = self._match(TokenType.INDENT)
        if indent is None:
            tok = self._cur()
            return ParseError("Se esperaba bloque de action", tok.line if tok else 0, tok.col if tok else 0)

        body_pos = self._pos_from(indent)
        mode: Optional[ModeClause] = None
        requires: Optional[RequiresClause] = None
        reversible: Optional[ReversibleClause] = None
        audit: Optional[AuditClause] = None
        escalation: Optional[EscalationClause] = None
        execute: Optional[ExecuteClause] = None

        while True:
            self._skip_newlines()
            if self._at(TokenType.DEDENT) or self._at(TokenType.EOF):
                self._match(TokenType.DEDENT)
                break

            tok = self._cur()
            if tok is None:
                break

            if tok.type == TokenType.MODE:
                self._advance()
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                mode_id = self._expect(TokenType.IDENTIFIER)
                if isinstance(mode_id, ParseError):
                    return mode_id
                if mode_id.value not in ("fast", "safe", "flow"):
                    return ParseError(f"Modo inválido: {mode_id.value}", mode_id.line, mode_id.col)
                from typing import Literal as L
                mode_val: L["fast", "safe", "flow"] = mode_id.value  # type: ignore[assignment]
                mode = ModeClause(position=self._pos_from(tok), mode=mode_val)
                self._skip_newlines()

            elif tok.type == TokenType.REQUIRES:
                self._advance()
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                expr = self._parse_expression()
                if isinstance(expr, ParseError):
                    return expr
                requires = RequiresClause(position=self._pos_from(tok), condition=expr)
                self._skip_newlines()

            elif tok.type == TokenType.REVERSIBLE:
                self._advance()
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                rev = self._parse_reversible_value()
                if isinstance(rev, ParseError):
                    return rev
                reversible = ReversibleClause(position=self._pos_from(tok), value=rev)
                self._skip_newlines()

            elif tok.type == TokenType.AUDIT:
                self._advance()
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                level_tok = self._expect(TokenType.IDENTIFIER)
                if isinstance(level_tok, ParseError):
                    return level_tok
                if level_tok.value not in ("full", "minimal", "silent"):
                    return ParseError(f"Nivel inválido: {level_tok.value}", level_tok.line, level_tok.col)
                from typing import Literal as L2
                audit_level: L2["full", "minimal", "silent"] = level_tok.value  # type: ignore[assignment]
                audit = AuditClause(position=self._pos_from(tok), level=audit_level)
                self._skip_newlines()

            elif tok.type == TokenType.ESCALATION:
                self._advance()
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                expr = self._parse_expression()
                if isinstance(expr, ParseError):
                    return expr
                escalation = EscalationClause(position=self._pos_from(tok), target=expr)
                self._skip_newlines()

            elif tok.type == TokenType.EXECUTE:
                self._advance()
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                exec_block = self._parse_block()
                if isinstance(exec_block, ParseError):
                    return exec_block
                execute = ExecuteClause(position=self._pos_from(tok), body=exec_block)
                self._skip_newlines()

            elif tok.type == TokenType.DOC_COMMENT:
                self._advance()
                self._skip_newlines()

            else:
                # Fin del bloque de action (no es una cláusula conocida)
                break

        return ActionBody(
            position=body_pos,
            mode=mode,
            requires=requires,
            reversible=reversible,
            audit=audit,
            escalation=escalation,
            execute=execute,
        )

    def _parse_reversible_value(self) -> Union[bool, str, Expression, ParseError]:
        tok = self._cur()
        if tok is None:
            return ParseError("Se esperaba valor de reversible", 0, 0)

        if tok.type == TokenType.TRUE:
            self._advance()
            return True
        if tok.type == TokenType.FALSE:
            self._advance()
            return False
        if tok.type == TokenType.TIME_LITERAL:
            val = tok.value
            self._advance()
            return val
        if tok.type == TokenType.IDENTIFIER and tok.value == "conditional":
            self._advance()
            lparen = self._expect(TokenType.LPAREN)
            if isinstance(lparen, ParseError):
                return lparen
            expr = self._parse_expression()
            if isinstance(expr, ParseError):
                return expr
            rparen = self._expect(TokenType.RPAREN)
            if isinstance(rparen, ParseError):
                return rparen
            return expr

        return ParseError(f"Valor de reversible inválido: {tok.value!r}", tok.line, tok.col)

    def _parse_agent_decl(self) -> Union[AgentDecl, ParseError]:
        agent_tok = self._advance()
        pos = self._pos_from(agent_tok)

        name_tok = self._expect(TokenType.IDENTIFIER)
        if isinstance(name_tok, ParseError):
            return name_tok

        colon = self._expect(TokenType.COLON)
        if isinstance(colon, ParseError):
            return colon

        body = self._parse_agent_body(pos)
        if isinstance(body, ParseError):
            return body

        return AgentDecl(position=pos, name=name_tok.value, body=body)

    def _parse_agent_body(self, decl_pos: SourcePosition) -> Union[AgentBody, ParseError]:
        self._skip_newlines()
        indent = self._match(TokenType.INDENT)
        if indent is None:
            tok = self._cur()
            return ParseError("Se esperaba bloque de agent", tok.line if tok else 0, tok.col if tok else 0)

        body_pos = self._pos_from(indent)
        watch: Optional[WatchClause] = None
        state: Optional[StateClause] = None
        on_clauses: list[OnClause] = []
        schedule: Optional[ScheduleClause] = None
        config: Optional[ConfigClause] = None

        while True:
            self._skip_newlines()
            if self._at(TokenType.DEDENT) or self._at(TokenType.EOF):
                self._match(TokenType.DEDENT)
                break

            tok = self._cur()
            if tok is None:
                break

            if tok.type == TokenType.WATCH:
                self._advance()
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                expr = self._parse_expression()
                if isinstance(expr, ParseError):
                    return expr
                watch = WatchClause(position=self._pos_from(tok), expression=expr)
                self._skip_newlines()

            elif tok.type == TokenType.STATE:
                self._advance()
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                state_result = self._parse_state_body(self._pos_from(tok))
                if isinstance(state_result, ParseError):
                    return state_result
                state = state_result

            elif tok.type == TokenType.ON:
                on_result = self._parse_on_clause()
                if isinstance(on_result, ParseError):
                    return on_result
                on_clauses.append(on_result)

            elif tok.type == TokenType.SCHEDULE:
                self._advance()
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                expr = self._parse_expression()
                if isinstance(expr, ParseError):
                    return expr
                schedule = ScheduleClause(position=self._pos_from(tok), expression=expr)
                self._skip_newlines()

            elif tok.type == TokenType.CONFIG:
                self._advance()
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                config_result = self._parse_config_body(self._pos_from(tok))
                if isinstance(config_result, ParseError):
                    return config_result
                config = config_result

            elif tok.type == TokenType.DOC_COMMENT:
                self._advance()
                self._skip_newlines()

            else:
                break

        return AgentBody(
            position=body_pos,
            watch=watch,
            state=state,
            on_clauses=tuple(on_clauses),
            schedule=schedule,
            config=config,
        )

    def _parse_state_body(self, pos: SourcePosition) -> Union[StateClause, ParseError]:
        self._skip_newlines()
        indent = self._match(TokenType.INDENT)
        if indent is None:
            tok = self._cur()
            return ParseError("Se esperaba bloque de state", tok.line if tok else 0, tok.col if tok else 0)

        fields: list[tuple[str, Optional[Type], Optional[Expression]]] = []

        while True:
            self._skip_newlines()
            if self._at(TokenType.DEDENT) or self._at(TokenType.EOF):
                self._match(TokenType.DEDENT)
                break

            tok = self._cur()
            if tok is None or tok.type in (TokenType.DEDENT, TokenType.EOF):
                break
            # Aceptar cualquier identificador o keyword como nombre de field
            if tok.type != TokenType.IDENTIFIER:
                # Solo continuar si parece ser un field (seguido de : o =)
                nxt = self._peek()
                if nxt is None or nxt.type not in (TokenType.COLON, TokenType.ASSIGN):
                    break

            field_name = tok.value
            self._advance()
            field_type: Optional[Type] = None
            field_default: Optional[Expression] = None

            if self._at(TokenType.COLON):
                self._advance()
                field_type = self._parse_type()  # type: ignore[assignment]
                if isinstance(field_type, ParseError):
                    return field_type

            if self._at(TokenType.ASSIGN):
                self._advance()
                field_default = self._parse_expression()  # type: ignore[assignment]
                if isinstance(field_default, ParseError):
                    return field_default

            fields.append((field_name, field_type, field_default))
            self._skip_newlines()

        return StateClause(position=pos, fields=tuple(fields))

    def _parse_config_body(self, pos: SourcePosition) -> Union[ConfigClause, ParseError]:
        self._skip_newlines()
        indent = self._match(TokenType.INDENT)
        if indent is None:
            tok = self._cur()
            return ParseError("Se esperaba bloque de config", tok.line if tok else 0, tok.col if tok else 0)

        settings: list[tuple[str, Expression]] = []

        while True:
            self._skip_newlines()
            if self._at(TokenType.DEDENT) or self._at(TokenType.EOF):
                self._match(TokenType.DEDENT)
                break

            tok = self._cur()
            if tok is None or tok.type in (TokenType.DEDENT, TokenType.EOF):
                break
            # Aceptar cualquier token como clave si va seguido de COLON
            next_tok = self._peek()
            if next_tok is None or next_tok.type != TokenType.COLON:
                break

            key = tok.value
            self._advance()
            colon = self._expect(TokenType.COLON)
            if isinstance(colon, ParseError):
                return colon
            val = self._parse_expression()
            if isinstance(val, ParseError):
                return val
            settings.append((key, val))
            self._skip_newlines()

        return ConfigClause(position=pos, settings=tuple(settings))

    def _parse_on_clause(self) -> Union[OnClause, ParseError]:
        on_tok = self._advance()
        pos = self._pos_from(on_tok)

        pattern = self._parse_expression()
        if isinstance(pattern, ParseError):
            return pattern

        condition: Optional[Expression] = None
        if self._at(TokenType.WHERE):
            self._advance()
            condition = self._parse_expression()  # type: ignore[assignment]
            if isinstance(condition, ParseError):
                return condition

        colon = self._expect(TokenType.COLON)
        if isinstance(colon, ParseError):
            return colon

        body = self._parse_block()
        if isinstance(body, ParseError):
            return body

        return OnClause(position=pos, pattern=pattern, condition=condition, body=body)

    # -----------------------------------------------------------------------
    # Parámetros
    # -----------------------------------------------------------------------

    def _parse_params(self) -> Union[tuple[Param, ...], ParseError]:
        params: list[Param] = []
        if self._at(TokenType.RPAREN):
            return ()

        while True:
            tok = self._cur()
            if tok is None or tok.type != TokenType.IDENTIFIER:
                break
            pos = self._pos_from(tok)
            name = tok.value
            self._advance()

            param_type: Optional[Type] = None
            if self._at(TokenType.COLON):
                self._advance()
                param_type = self._parse_type()  # type: ignore[assignment]
                if isinstance(param_type, ParseError):
                    return param_type

            default: Optional[Expression] = None
            if self._at(TokenType.ASSIGN):
                self._advance()
                default = self._parse_expression()  # type: ignore[assignment]
                if isinstance(default, ParseError):
                    return default

            params.append(Param(position=pos, name=name, type_annotation=param_type, default=default))

            if not self._at(TokenType.COMMA):
                break
            self._advance()

        return tuple(params)

    # -----------------------------------------------------------------------
    # Tipos
    # -----------------------------------------------------------------------

    def _parse_type(self) -> Union[Type, ParseError]:
        left = self._parse_simple_type()
        if isinstance(left, ParseError):
            return left

        if self._at(TokenType.PIPE):
            self._advance()
            right = self._parse_type()
            if isinstance(right, ParseError):
                return right
            return UnionType(position=left.position, left=left, right=right)

        return left

    def _parse_simple_type(self) -> Union[Type, ParseError]:
        tok = self._cur()
        if tok is None:
            return ParseError("Se esperaba tipo", 0, 0)

        pos = self._pos_from(tok)
        primitives = {"text", "number", "time", "boolean", "any"}

        if tok.type == TokenType.IDENTIFIER and tok.value in primitives:
            self._advance()
            from typing import Literal as L
            prim_name: L["text", "number", "time", "boolean", "any"] = tok.value  # type: ignore[assignment]
            return PrimitiveType(position=pos, name=prim_name)

        if tok.type == TokenType.IDENTIFIER:
            base = tok.value
            self._advance()
            if self._at(TokenType.LT):
                self._advance()
                args: list[Type] = []
                arg = self._parse_type()
                if isinstance(arg, ParseError):
                    return arg
                args.append(arg)
                while self._at(TokenType.COMMA):
                    self._advance()
                    arg2 = self._parse_type()
                    if isinstance(arg2, ParseError):
                        return arg2
                    args.append(arg2)
                gt = self._expect(TokenType.GT)
                if isinstance(gt, ParseError):
                    return gt
                return ParametrizedType(position=pos, base=base, args=tuple(args))
            # Tipo no primitivo como identificador → any
            return PrimitiveType(position=pos, name="any")

        return ParseError(f"Tipo inválido: {tok.type.name}", tok.line, tok.col)

    # -----------------------------------------------------------------------
    # Statements
    # -----------------------------------------------------------------------

    def _parse_statement(self) -> Union[Statement, ParseError]:
        self._skip_newlines()
        tok = self._cur()
        if tok is None:
            return PassStatement(position=SourcePosition(line=0, col=0))

        if tok.type == TokenType.RETURN:
            return self._parse_return()
        if tok.type == TokenType.PASS:
            self._advance()
            self._skip_newlines()
            return PassStatement(position=self._pos_from(tok))
        if tok.type == TokenType.IF:
            return self._parse_if()
        if tok.type == TokenType.MATCH:
            return self._parse_match()
        if tok.type == TokenType.FOR:
            return self._parse_for()
        if tok.type == TokenType.RESOLVE:
            result = self._parse_resolve()
            self._skip_newlines()
            return result
        if tok.type == TokenType.PRINT:
            return self._parse_print()
        if tok.type == TokenType.UNDO:
            return self._parse_undo()

        # mode: <value> inside fn/action bodies — consume and ignore at statement level
        if tok.type == TokenType.MODE:
            self._advance()
            if self._at(TokenType.COLON):
                self._advance()
                if self._cur() and self._cur().type == TokenType.IDENTIFIER:  # type: ignore[union-attr]
                    self._advance()
            self._skip_newlines()
            return PassStatement(position=self._pos_from(tok))

        return self._parse_assignment_or_expr()

    def _parse_return(self) -> Union[ReturnStatement, ParseError]:
        tok = self._advance()
        pos = self._pos_from(tok)

        next_tok = self._cur()
        if next_tok is None or next_tok.type in (TokenType.NEWLINE, TokenType.DEDENT, TokenType.EOF):
            self._skip_newlines()
            return ReturnStatement(position=pos)

        if next_tok.type in (
            TokenType.NUMBER, TokenType.STRING, TokenType.IDENTIFIER, TokenType.TRUE, TokenType.FALSE,
            TokenType.MONEY_LITERAL, TokenType.TIME_LITERAL, TokenType.LPAREN, TokenType.LBRACKET,
            TokenType.MINUS, TokenType.NOT, TokenType.INTERP_START,
        ):
            expr = self._parse_expression()
            if isinstance(expr, ParseError):
                return expr
            self._skip_newlines()
            return ReturnStatement(position=pos, value=expr)

        self._skip_newlines()
        return ReturnStatement(position=pos)

    def _parse_if(self) -> Union[IfStatement, ParseError]:
        tok = self._advance()
        pos = self._pos_from(tok)

        condition = self._parse_expression()
        if isinstance(condition, ParseError):
            return condition

        colon = self._expect(TokenType.COLON)
        if isinstance(colon, ParseError):
            return colon

        then_block = self._parse_block()
        if isinstance(then_block, ParseError):
            return then_block

        else_block: Optional[Block] = None
        # Verificar else en la misma línea del DEDENT o después
        self._skip_newlines()
        if self._at(TokenType.ELSE):
            self._advance()
            else_colon = self._expect(TokenType.COLON)
            if isinstance(else_colon, ParseError):
                return else_colon
            else_block = self._parse_block()  # type: ignore[assignment]
            if isinstance(else_block, ParseError):
                return else_block

        return IfStatement(position=pos, condition=condition, then_block=then_block, else_block=else_block)

    def _parse_match(self) -> Union[MatchStatement, ParseError]:
        tok = self._advance()
        pos = self._pos_from(tok)

        subject = self._parse_expression()
        if isinstance(subject, ParseError):
            return subject

        colon = self._expect(TokenType.COLON)
        if isinstance(colon, ParseError):
            return colon

        self._skip_newlines()
        indent = self._match(TokenType.INDENT)
        if indent is None:
            tok2 = self._cur()
            return ParseError("Se esperaba bloque de match", tok2.line if tok2 else 0, tok2.col if tok2 else 0)

        arms: list[MatchArm] = []

        while True:
            self._skip_newlines()
            if self._at(TokenType.DEDENT) or self._at(TokenType.EOF):
                self._match(TokenType.DEDENT)
                break

            tok2 = self._cur()
            if tok2 is None:
                break
            arm_pos = self._pos_from(tok2)

            pattern = self._parse_expression()
            if isinstance(pattern, ParseError):
                return pattern

            arrow = self._expect(TokenType.ARROW)
            if isinstance(arrow, ParseError):
                return arrow

            # Body inline o bloque
            next_t = self._cur()
            arm_body: Union[Block, Expression]
            STMT_LIKE = {
                TokenType.PRINT, TokenType.IF, TokenType.FOR,
                TokenType.MATCH, TokenType.RESOLVE, TokenType.UNDO, TokenType.RETURN,
            }
            if next_t and next_t.type not in (TokenType.NEWLINE, TokenType.INDENT):
                if next_t.type in STMT_LIKE:
                    # Statement keyword as arm body → wrap in block
                    stmt = self._parse_statement()
                    if isinstance(stmt, ParseError):
                        return stmt
                    arm_body = Block(position=arm_pos, statements=(stmt,))
                else:
                    expr = self._parse_expression()
                    if isinstance(expr, ParseError):
                        return expr
                    arm_body = expr
                self._skip_newlines()
            else:
                block = self._parse_block()
                if isinstance(block, ParseError):
                    return block
                arm_body = block

            arms.append(MatchArm(position=arm_pos, pattern=pattern, body=arm_body))

        return MatchStatement(position=pos, subject=subject, arms=tuple(arms))

    def _parse_for(self) -> Union[ForStatement, ParseError]:
        tok = self._advance()
        pos = self._pos_from(tok)

        target_tok = self._expect(TokenType.IDENTIFIER)
        if isinstance(target_tok, ParseError):
            return target_tok

        in_tok = self._expect(TokenType.IN)
        if isinstance(in_tok, ParseError):
            return in_tok

        iterable = self._parse_expression()
        if isinstance(iterable, ParseError):
            return iterable

        colon = self._expect(TokenType.COLON)
        if isinstance(colon, ParseError):
            return colon

        body = self._parse_block()
        if isinstance(body, ParseError):
            return body

        return ForStatement(position=pos, target=target_tok.value, iterable=iterable, body=body)

    def _parse_resolve(self) -> Union[ResolveBlock, ParseError]:
        tok = self._advance()
        pos = self._pos_from(tok)

        lparen = self._expect(TokenType.LPAREN)
        if isinstance(lparen, ParseError):
            return lparen

        subject = self._parse_expression()
        if isinstance(subject, ParseError):
            return subject

        rparen = self._expect(TokenType.RPAREN)
        if isinstance(rparen, ParseError):
            return rparen

        lbrace = self._expect(TokenType.LBRACE)
        if isinstance(lbrace, ParseError):
            return lbrace

        strategies: list[StrategyClause] = []
        self._skip_newlines()
        # Handle indented body: { NEWLINE INDENT strategies... DEDENT }
        if self._at(TokenType.INDENT):
            self._advance()

        while not self._at(TokenType.RBRACE):
            self._skip_newlines()
            if self._at(TokenType.DEDENT):
                self._advance()
            if self._at(TokenType.RBRACE) or self._cur() is None:
                break

            tok2 = self._cur()
            if tok2 is None:
                break
            strat_pos = self._pos_from(tok2)

            name_tok = self._expect(TokenType.IDENTIFIER)
            if isinstance(name_tok, ParseError):
                return name_tok

            colon = self._expect(TokenType.COLON)
            if isinstance(colon, ParseError):
                return colon

            body_expr = self._parse_expression()
            if isinstance(body_expr, ParseError):
                return body_expr

            strategies.append(StrategyClause(position=strat_pos, name=name_tok.value, body=body_expr))
            self._skip_newlines()

        rbrace = self._expect(TokenType.RBRACE)
        if isinstance(rbrace, ParseError):
            return rbrace

        return ResolveBlock(position=pos, subject=subject, strategies=tuple(strategies))

    def _parse_print(self) -> Union[PrintStatement, ParseError]:
        tok = self._advance()
        pos = self._pos_from(tok)
        expr = self._parse_expression()
        if isinstance(expr, ParseError):
            return expr
        self._skip_newlines()
        return PrintStatement(position=pos, value=expr)

    def _parse_undo(self) -> Union[UndoStatement, ParseError]:
        tok = self._advance()
        pos = self._pos_from(tok)
        lparen = self._expect(TokenType.LPAREN)
        if isinstance(lparen, ParseError):
            return lparen

        key_tok = self._expect(TokenType.IDENTIFIER)
        if isinstance(key_tok, ParseError):
            return key_tok
        eq = self._expect(TokenType.ASSIGN)
        if isinstance(eq, ParseError):
            return eq
        val = self._parse_expression()
        if isinstance(val, ParseError):
            return val

        rparen = self._expect(TokenType.RPAREN)
        if isinstance(rparen, ParseError):
            return rparen

        self._skip_newlines()
        return UndoStatement(position=pos, action_id=val)

    def _parse_assignment_or_expr(self) -> Union[Statement, ParseError]:
        tok = self._cur()
        if tok is None:
            return ParseError("Se esperaba statement", 0, 0)

        # Look-ahead para assignment: IDENTIFIER ASSIGN
        if tok.type == TokenType.IDENTIFIER:
            next_tok = self._peek()
            if next_tok and next_tok.type == TokenType.ASSIGN:
                return self._parse_assignment()

        # Expresión/pipeline
        pos = self._pos_from(tok)
        expr = self._parse_expression()
        if isinstance(expr, ParseError):
            return expr

        # Pipeline: mismo línea o multi-línea con continuación
        expr = self._try_parse_pipeline_continuation(expr)
        if isinstance(expr, ParseError):
            return expr

        # Consume optional because annotation (e.g. transfer.money(...) because "reason")
        if self._at(TokenType.BECAUSE):
            self._advance()
            if self._at(TokenType.STRING):
                self._advance()

        self._skip_newlines()
        return ExpressionStatement(position=pos, expression=expr)

    def _parse_assignment(self) -> Union[Assignment, ParseError]:
        tok = self._cur()
        pos = self._pos_from(tok)
        name = tok.value  # type: ignore[union-attr]
        self._advance()  # consume IDENTIFIER
        self._advance()  # consume ASSIGN

        expr = self._parse_expression()
        if isinstance(expr, ParseError):
            return expr

        # Manejo de pipeline multi-línea: NEWLINE + (INDENT)? + PIPE
        expr = self._try_parse_pipeline_continuation(expr)
        if isinstance(expr, ParseError):
            return expr

        because: Optional[BecauseAnnotation] = None
        if self._at(TokenType.BECAUSE):
            self._advance()
            reason_tok = self._cur()
            if reason_tok and reason_tok.type == TokenType.STRING:
                reason = reason_tok.value
                self._advance()
                because = BecauseAnnotation(position=self._pos_from(reason_tok), reason=reason)

        self._skip_newlines()
        return Assignment(position=pos, target=name, value=expr, because=because)

    def _try_parse_pipeline_continuation(
        self, first_step: Expression
    ) -> Union[Expression, ParseError]:
        """Si hay NEWLINE + (INDENT)? + PIPE, parsea pipeline multi-línea.

        Consume NEWLINE e INDENT antes de cada PIPE, pero NO consume el DEDENT
        al final — lo deja para que el bloque padre lo cierre.
        """
        def _peek_next_non_nl_indent() -> Optional[Token]:
            """Retorna el primer token ignorando NEWLINE e INDENT desde pos actual."""
            i = self._pos
            while i < len(self._tokens) and self._tokens[i].type in (
                TokenType.NEWLINE, TokenType.INDENT
            ):
                i += 1
            return self._tokens[i] if i < len(self._tokens) else None

        def _at_pipe_cont() -> bool:
            tok = _peek_next_non_nl_indent()
            return tok is not None and tok.type == TokenType.PIPE

        if not _at_pipe_cont() and not self._at(TokenType.PIPE):
            return first_step

        steps = [first_step]
        indent_depth = 0
        while self._at(TokenType.PIPE) or _at_pipe_cont():
            # Consumir NEWLINEs e INDENTs antes del PIPE
            while self._at(TokenType.NEWLINE):
                self._advance()
            while self._at(TokenType.INDENT):
                self._advance()
                indent_depth += 1
            if not self._at(TokenType.PIPE):
                break
            self._advance()  # consume PIPE
            step = self._parse_expression()
            if isinstance(step, ParseError):
                return step
            steps.append(step)
        # Consumir NEWLINEs y DEDENTs correspondientes a los INDENTs consumidos
        while self._at(TokenType.NEWLINE):
            self._advance()
        for _ in range(indent_depth):
            self._match(TokenType.DEDENT)
        pos = first_step.position
        return Pipeline(position=pos, steps=tuple(steps))

    # -----------------------------------------------------------------------
    # Expresiones
    # -----------------------------------------------------------------------

    def _parse_expression(self) -> Union[Expression, ParseError]:
        return self._parse_or()

    def _parse_or(self) -> Union[Expression, ParseError]:
        left = self._parse_and()
        if isinstance(left, ParseError):
            return left
        while self._at(TokenType.OR):
            op_tok = self._advance()
            right = self._parse_and()
            if isinstance(right, ParseError):
                return right
            left = BinaryOp(position=self._pos_from(op_tok), op="or", left=left, right=right)
        return left

    def _parse_and(self) -> Union[Expression, ParseError]:
        left = self._parse_not()
        if isinstance(left, ParseError):
            return left
        while self._at(TokenType.AND):
            op_tok = self._advance()
            right = self._parse_not()
            if isinstance(right, ParseError):
                return right
            left = BinaryOp(position=self._pos_from(op_tok), op="and", left=left, right=right)
        return left

    def _parse_not(self) -> Union[Expression, ParseError]:
        if self._at(TokenType.NOT):
            op_tok = self._advance()
            operand = self._parse_not()
            if isinstance(operand, ParseError):
                return operand
            return UnaryOp(position=self._pos_from(op_tok), op="not", operand=operand)
        return self._parse_compare()

    def _parse_compare(self) -> Union[Expression, ParseError]:
        left = self._parse_add()
        if isinstance(left, ParseError):
            return left
        while self._at(TokenType.GT, TokenType.LT, TokenType.GTE, TokenType.LTE, TokenType.EQ, TokenType.NEQ, TokenType.IN):
            op_tok = self._advance()
            right = self._parse_add()
            if isinstance(right, ParseError):
                return right
            left = BinaryOp(position=self._pos_from(op_tok), op=op_tok.value, left=left, right=right)
        return left

    def _parse_add(self) -> Union[Expression, ParseError]:
        left = self._parse_mul()
        if isinstance(left, ParseError):
            return left
        while self._at(TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            right = self._parse_mul()
            if isinstance(right, ParseError):
                return right
            left = BinaryOp(position=self._pos_from(op_tok), op=op_tok.value, left=left, right=right)
        return left

    def _parse_mul(self) -> Union[Expression, ParseError]:
        left = self._parse_unary()
        if isinstance(left, ParseError):
            return left
        while self._at(TokenType.STAR, TokenType.SLASH):
            op_tok = self._advance()
            right = self._parse_unary()
            if isinstance(right, ParseError):
                return right
            left = BinaryOp(position=self._pos_from(op_tok), op=op_tok.value, left=left, right=right)
        return left

    def _parse_unary(self) -> Union[Expression, ParseError]:
        if self._at(TokenType.MINUS):
            op_tok = self._advance()
            operand = self._parse_postfix()
            if isinstance(operand, ParseError):
                return operand
            return UnaryOp(position=self._pos_from(op_tok), op="-", operand=operand)
        return self._parse_postfix()

    def _parse_postfix(self) -> Union[Expression, ParseError]:
        expr = self._parse_primary()
        if isinstance(expr, ParseError):
            return expr

        while True:
            if self._at(TokenType.DOT):
                self._advance()
                field_tok = self._expect(TokenType.IDENTIFIER)
                if isinstance(field_tok, ParseError):
                    return field_tok
                dot_expr = DotAccess(position=expr.position, obj=expr, field=field_tok.value)
                if self._at(TokenType.LPAREN):
                    self._advance()
                    call_args_result = self._parse_call_args()
                    if isinstance(call_args_result, ParseError):
                        return call_args_result
                    call_args, call_kwargs = call_args_result
                    rparen = self._expect(TokenType.RPAREN)
                    if isinstance(rparen, ParseError):
                        return rparen
                    expr = FunctionCall(position=expr.position, name=field_tok.value, args=(dot_expr, *call_args), kwargs=call_kwargs)
                else:
                    expr = dot_expr

            elif self._at(TokenType.LBRACKET):
                self._advance()
                index = self._parse_expression()
                if isinstance(index, ParseError):
                    return index
                rbracket = self._expect(TokenType.RBRACKET)
                if isinstance(rbracket, ParseError):
                    return rbracket
                expr = IndexAccess(position=expr.position, obj=expr, index=index)

            elif self._at(TokenType.LPAREN):
                self._advance()
                call_args_result = self._parse_call_args()
                if isinstance(call_args_result, ParseError):
                    return call_args_result
                call_args, call_kwargs = call_args_result
                rparen = self._expect(TokenType.RPAREN)
                if isinstance(rparen, ParseError):
                    return rparen
                name = expr.name if isinstance(expr, Identifier) else "call"
                expr = FunctionCall(position=expr.position, name=name, args=call_args, kwargs=call_kwargs)

            elif self._at(TokenType.QUESTION):
                self._advance()
                expr = UnaryOp(position=expr.position, op="?", operand=expr)

            else:
                break

        return expr

    def _parse_call_args(self) -> Union[tuple[tuple[Expression, ...], tuple[tuple[str, Expression], ...]], ParseError]:
        args: list[Expression] = []
        kwargs: list[tuple[str, Expression]] = []

        # Enable lambda parsing (e -> expr) inside call argument lists
        prev_allow_lambda = self._allow_lambda
        self._allow_lambda = True

        # Skip newlines and optional indent for multi-line calls like:
        # func(
        #   from=x,
        #   to=y,
        # )
        self._skip_newlines()
        if self._at(TokenType.INDENT):
            self._advance()

        if self._at(TokenType.RPAREN):
            return (), ()

        while not self._at(TokenType.RPAREN):
            # Skip whitespace between arguments in multi-line calls
            self._skip_newlines()
            if self._at(TokenType.DEDENT):
                self._advance()
            if self._at(TokenType.RPAREN) or self._cur() is None:
                break

            tok = self._cur()
            if tok is None:
                break

            # Kwarg: any-token ASSIGN expr
            # Permitir keywords como nombres de param (e.g. from=, to=, in=)
            next_tok = self._peek()
            if tok.type != TokenType.RPAREN and next_tok and next_tok.type == TokenType.ASSIGN:
                key = tok.value
                self._advance()
                self._advance()
                val = self._parse_expression()
                if isinstance(val, ParseError):
                    return val
                kwargs.append((key, val))
                if self._at(TokenType.COMMA):
                    self._advance()
                    self._skip_newlines()
                    if self._at(TokenType.INDENT):
                        self._advance()
                continue

            val = self._parse_expression()
            if isinstance(val, ParseError):
                return val
            args.append(val)

            if self._at(TokenType.COMMA):
                self._advance()
                self._skip_newlines()
                if self._at(TokenType.INDENT):
                    self._advance()
            else:
                break

        # Consume trailing newlines/dedents so caller sees RPAREN next
        self._skip_newlines()
        while self._at(TokenType.DEDENT):
            self._advance()
        self._skip_newlines()

        self._allow_lambda = prev_allow_lambda
        return tuple(args), tuple(kwargs)

    def _parse_primary(self) -> Union[Expression, ParseError]:
        tok = self._cur()
        if tok is None:
            return ParseError("Se esperaba expresión", 0, 0)

        pos = self._pos_from(tok)

        if tok.type == TokenType.NUMBER:
            self._advance()
            return NumberLiteral(position=pos, value=tok.value)

        if tok.type == TokenType.MONEY_LITERAL:
            self._advance()
            val = tok.value
            symbol = val[0]
            rest = val[1:]
            parts = rest.split()
            amount = parts[0] if parts else "0"
            currency_map = {"$": "USD", "€": "EUR", "£": "GBP"}
            currency = parts[1] if len(parts) > 1 else currency_map.get(symbol, "USD")
            return MoneyLiteral(position=pos, value=val, amount=amount, currency=currency)

        if tok.type == TokenType.TIME_LITERAL:
            self._advance()
            return TimeLiteral(position=pos, value=tok.value)

        if tok.type == TokenType.TRUE:
            self._advance()
            return BooleanLiteral(position=pos, value=True)

        if tok.type == TokenType.FALSE:
            self._advance()
            return BooleanLiteral(position=pos, value=False)

        if tok.type == TokenType.STRING:
            self._advance()
            # Si va seguido de INTERP_START, es parte de string interpolado
            if self._at(TokenType.INTERP_START):
                interp_parts: list[Union[str, Expression]] = [tok.value]
                while self._at(TokenType.INTERP_START):
                    self._advance()  # consume INTERP_START
                    expr_interp = self._parse_expression()
                    if isinstance(expr_interp, ParseError):
                        return expr_interp
                    close = self._expect(TokenType.INTERP_END)
                    if isinstance(close, ParseError):
                        return close
                    interp_parts.append(expr_interp)
                    if self._at(TokenType.STRING):
                        interp_parts.append(self._advance().value)
                return StringInterpolation(position=pos, parts=tuple(interp_parts))
            return StringLiteral(position=pos, value=tok.value)

        if tok.type == TokenType.INTERP_START:
            return self._parse_string_interp_from_tokens(pos)

        if tok.type == TokenType.PASS:
            self._advance()
            return Identifier(position=pos, name="pass")

        if tok.type == TokenType.IDENTIFIER:
            name = tok.value
            self._advance()
            # Lambda: identifier -> expression  (e.g. e -> e.priority > 0.7)
            # Only allowed inside call argument lists to avoid conflict with match arm arrows.
            if self._allow_lambda and self._at(TokenType.ARROW):
                self._advance()  # consume ->
                body = self._parse_expression()
                if isinstance(body, ParseError):
                    return body
                param_node = Identifier(position=pos, name=name)
                return FunctionCall(
                    position=pos,
                    name="__lambda__",
                    args=(param_node, body),
                    kwargs=(),
                )
            return Identifier(position=pos, name=name)

        # Keywords used as identifiers in dot-chains/capability paths
        if tok.type in (TokenType.AUDIT, TokenType.MODE, TokenType.STATE):
            self._advance()
            return Identifier(position=pos, name=tok.value)

        # Shorthand dot notation: .field means current-item.field (e.g. sort_by(.relevance))
        if tok.type == TokenType.DOT:
            self._advance()
            field_tok = self._cur()
            if field_tok and field_tok.type == TokenType.IDENTIFIER:
                self._advance()
                placeholder = Identifier(position=pos, name="_")
                return DotAccess(position=pos, obj=placeholder, field=field_tok.value)
            return ParseError("Se esperaba nombre de campo después de '.'", tok.line, tok.col)

        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            if isinstance(expr, ParseError):
                return expr
            rparen = self._expect(TokenType.RPAREN)
            if isinstance(rparen, ParseError):
                return rparen
            return expr

        if tok.type == TokenType.LBRACKET:
            self._advance()
            items: list[Expression] = []
            while not self._at(TokenType.RBRACKET):
                if self._cur() is None:
                    break
                item = self._parse_expression()
                if isinstance(item, ParseError):
                    return item
                items.append(item)
                if not self._at(TokenType.COMMA):
                    break
                self._advance()
            rbracket = self._expect(TokenType.RBRACKET)
            if isinstance(rbracket, ParseError):
                return rbracket
            return FunctionCall(position=pos, name="__list__", args=tuple(items), kwargs=())

        if tok.type == TokenType.LBRACE:
            self._advance()
            pairs: list[tuple[Expression, Expression]] = []
            self._skip_ws()
            while not self._at(TokenType.RBRACE):
                if self._cur() is None:
                    break
                k = self._parse_expression()
                if isinstance(k, ParseError):
                    return k
                colon = self._expect(TokenType.COLON)
                if isinstance(colon, ParseError):
                    return colon
                v = self._parse_expression()
                if isinstance(v, ParseError):
                    return v
                pairs.append((k, v))
                if not self._at(TokenType.COMMA):
                    self._skip_ws()
                    break
                self._advance()
                self._skip_ws()
            self._skip_ws()
            rbrace = self._expect(TokenType.RBRACE)
            if isinstance(rbrace, ParseError):
                return rbrace
            flat_args = [item for pair in pairs for item in pair]
            return FunctionCall(position=pos, name="__dict__", args=tuple(flat_args), kwargs=())

        if tok.type == TokenType.RESOLVE:
            return self._parse_resolve()  # type: ignore[return-value]

        if tok.type == TokenType.UNDO:
            # undo(action_id=x) as expression (e.g., result = undo(...))
            stmt = self._parse_undo()
            if isinstance(stmt, ParseError):
                return stmt
            # Represent as FunctionCall so it's usable as Expression
            action_id_expr = getattr(stmt, "action_id", None)
            args = (action_id_expr,) if action_id_expr is not None else ()
            return FunctionCall(position=pos, name="undo", args=args, kwargs=())

        return ParseError(
            message=f"Token inesperado en expresión: {tok.type.name} ({tok.value!r})",
            line=tok.line,
            col=tok.col,
            code="LMN-0010",
        )

    def _parse_string_interp_from_tokens(self, pos: SourcePosition) -> Union[StringInterpolation, ParseError]:
        """Parsea STRING con partes interpoladas desde tokens del lexer."""
        parts: list[Union[str, Expression]] = []

        # El lexer produce: [STRING] INTERP_START expr INTERP_END [STRING] ...
        # Retrocedemos si hay STRING antes
        if self._pos > 0 and self._tokens[self._pos - 1].type == TokenType.STRING:
            parts.append(self._tokens[self._pos - 1].value)

        tok = self._cur()
        while tok is not None:
            if tok.type == TokenType.STRING:
                parts.append(tok.value)
                self._advance()
            elif tok.type == TokenType.INTERP_START:
                self._advance()
                expr = self._parse_expression()
                if isinstance(expr, ParseError):
                    return expr
                parts.append(expr)
                close = self._expect(TokenType.INTERP_END)
                if isinstance(close, ParseError):
                    return close
            else:
                break
            tok = self._cur()

        return StringInterpolation(position=pos, parts=tuple(parts))


def parse(source: str) -> Union[Program, ParseError]:
    """Parsea source string y retorna Program o ParseError."""
    tokens_or_err = tokenize(source)
    if isinstance(tokens_or_err, LexError):
        return ParseError(
            message=tokens_or_err.message,
            line=tokens_or_err.line,
            col=tokens_or_err.col,
            code=tokens_or_err.code,
        )

    parser = Parser(tokens_or_err)
    return parser.parse()
