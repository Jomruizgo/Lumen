"""Lexer para el lenguaje Lumen.

Convierte source text → lista de tokens.
Errores: LMN-0010 (SyntaxError), LMN-0011 (IndentationError).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Union


class TokenType(Enum):
    # Keywords
    ACTION = auto()
    AGENT = auto()
    FN = auto()
    USE = auto()
    IMPORT = auto()
    IF = auto()
    ELSE = auto()
    MATCH = auto()
    FOR = auto()
    RETURN = auto()
    RESOLVE = auto()
    BECAUSE = auto()
    MODE = auto()
    REQUIRES = auto()
    EXECUTE = auto()
    REVERSIBLE = auto()
    AUDIT = auto()
    WATCH = auto()
    ON = auto()
    STATE = auto()
    CONFIG = auto()
    SCHEDULE = auto()
    TRUE = auto()
    FALSE = auto()
    PASS = auto()
    IN = auto()
    WHERE = auto()
    AS = auto()
    FROM = auto()
    NOT = auto()
    AND = auto()
    OR = auto()
    COLLECT = auto()
    UNDO = auto()
    ESCALATION = auto()
    PRINT = auto()

    # Literals
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PIPE = auto()
    ARROW = auto()       # ->
    FAT_ARROW = auto()   # =>
    GT = auto()
    LT = auto()
    GTE = auto()
    LTE = auto()
    EQ = auto()          # ==
    NEQ = auto()         # !=
    ASSIGN = auto()      # =
    QUESTION = auto()    # ?

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    COLON = auto()
    DOT = auto()
    AT = auto()

    # Special
    INDENT = auto()
    DEDENT = auto()
    NEWLINE = auto()
    EOF = auto()

    # Semantic
    TIME_LITERAL = auto()   # "5min", "2h", "7d"
    MONEY_LITERAL = auto()  # "$100 USD", "€50 EUR"
    INTERP_START = auto()   # "${" dentro de string
    INTERP_END = auto()     # "}" que cierra interpolación
    VERSION = auto()        # "@lumen 1.0"
    DOC_COMMENT = auto()    # "#:"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int


@dataclass
class LexError:
    message: str
    line: int
    col: int
    code: str = "LMN-0010"


# Mapa de keywords
KEYWORDS: dict[str, TokenType] = {
    "action": TokenType.ACTION,
    "agent": TokenType.AGENT,
    "fn": TokenType.FN,
    "use": TokenType.USE,
    "import": TokenType.IMPORT,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "match": TokenType.MATCH,
    "for": TokenType.FOR,
    "return": TokenType.RETURN,
    "resolve": TokenType.RESOLVE,
    "because": TokenType.BECAUSE,
    "mode": TokenType.MODE,
    "requires": TokenType.REQUIRES,
    "execute": TokenType.EXECUTE,
    "reversible": TokenType.REVERSIBLE,
    "audit": TokenType.AUDIT,
    "watch": TokenType.WATCH,
    "on": TokenType.ON,
    "state": TokenType.STATE,
    "config": TokenType.CONFIG,
    "schedule": TokenType.SCHEDULE,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "pass": TokenType.PASS,
    "in": TokenType.IN,
    "where": TokenType.WHERE,
    "as": TokenType.AS,
    "from": TokenType.FROM,
    "not": TokenType.NOT,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "collect": TokenType.COLLECT,
    "undo": TokenType.UNDO,
    "escalation": TokenType.ESCALATION,
    "print": TokenType.PRINT,
}

# Unidades de tiempo válidas (orden importa: min antes de m si lo hubiera)
TIME_UNITS = ["min", "h", "d", "w", "y", "s"]

# Símbolos de moneda
CURRENCY_SYMBOLS: dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
}


def tokenize(source: str) -> Union[list[Token], LexError]:
    """Convierte source string en lista de tokens.

    Retorna LexError en caso de error léxico.
    """
    tokens: list[Token] = []
    lines = source.splitlines(keepends=True)

    # Pila de indentación: empieza en columna 0
    indent_stack: list[int] = [0]
    # Buffer de indentación pendiente al inicio de línea
    line_num = 0
    pos = 0  # posición absoluta en source

    # Procesamos línea a línea para manejar INDENT/DEDENT
    i = 0  # índice de carácter en source
    total = len(source)

    # Estado general
    current_line = 1
    current_col = 1

    # Convertimos a lista de caracteres con metadatos usando un enfoque de cursor
    result = _lex_source(source)
    return result


def _lex_source(source: str) -> Union[list[Token], LexError]:
    """Implementación principal del lexer."""
    tokens: list[Token] = []
    indent_stack: list[int] = [0]

    lines = source.split("\n")
    # Reconstruimos la fuente línea a línea
    line_num = 0

    # Procesamos una línea a la vez
    line_tokens: list[list[Token]] = []

    for raw_line in lines:
        line_num += 1
        line_result = _process_line(raw_line, line_num, indent_stack, tokens)
        if isinstance(line_result, LexError):
            return line_result

    # Emitir DEDENT finales
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Token(TokenType.DEDENT, "", line_num, 1))

    tokens.append(Token(TokenType.EOF, "", line_num, 1))
    return tokens


def _process_line(
    line: str,
    line_num: int,
    indent_stack: list[int],
    tokens: list[Token],
) -> None | LexError:
    """Procesa una línea del source y agrega tokens a la lista."""
    # Línea vacía o solo espacios → ignorar (no emitir NEWLINE para líneas vacías)
    stripped = line.rstrip("\r\n")

    # Línea completamente vacía o solo whitespace → ignorar
    if not stripped.strip():
        return None

    # Calcular indentación
    col = 1
    indent_chars = 0
    for ch in stripped:
        if ch == " ":
            indent_chars += 1
        elif ch == "\t":
            # Tabs no permitidos → LMN-0011
            return LexError(
                message="Se encontró un TAB en la indentación. Lumen usa 2 espacios.",
                line=line_num,
                col=1,
                code="LMN-0011",
            )
        else:
            break

    content = stripped[indent_chars:]

    # Ignorar líneas que son solo comentarios (no doc-comments)
    if content.startswith("#") and not content.startswith("#:"):
        return None

    # Manejar INDENT/DEDENT
    current_indent = indent_stack[-1]

    if indent_chars > current_indent:
        # Verificar múltiplos de 2
        if indent_chars % 2 != 0:
            return LexError(
                message=f"Indentación inválida: {indent_chars} espacios. Lumen usa múltiplos de 2.",
                line=line_num,
                col=1,
                code="LMN-0011",
            )
        indent_stack.append(indent_chars)
        tokens.append(Token(TokenType.INDENT, "", line_num, 1))
    elif indent_chars < current_indent:
        # Desindentación: puede emitir múltiples DEDENTs
        while indent_stack[-1] > indent_chars:
            indent_stack.pop()
            tokens.append(Token(TokenType.DEDENT, "", line_num, 1))
        if indent_stack[-1] != indent_chars:
            return LexError(
                message=f"Indentación inconsistente en línea {line_num}.",
                line=line_num,
                col=1,
                code="LMN-0011",
            )

    # Tokenizar el contenido de la línea
    result = _tokenize_line(content, line_num, indent_chars + 1)
    if isinstance(result, LexError):
        return result

    tokens.extend(result)

    # Emitir NEWLINE al final (si hay tokens en la línea)
    if result:
        tokens.append(Token(TokenType.NEWLINE, "\n", line_num, len(stripped) + 1))

    return None


def _tokenize_line(
    content: str, line_num: int, start_col: int
) -> Union[list[Token], LexError]:
    """Tokeniza el contenido de una línea (sin indentación)."""
    tokens: list[Token] = []
    i = 0
    n = len(content)
    col = start_col

    while i < n:
        ch = content[i]

        # Espacios → ignorar
        if ch == " ":
            i += 1
            col += 1
            continue

        # Doc comment #:
        if content[i : i + 2] == "#:":
            comment_text = content[i + 2 :].strip()
            tokens.append(Token(TokenType.DOC_COMMENT, comment_text, line_num, col))
            break  # resto de línea

        # Comentario normal # → ignorar resto de línea
        if ch == "#":
            break

        # VERSION: @lumen número.número
        if content[i : i + 6] == "@lumen":
            rest = content[i + 6 :]
            m = re.match(r"\s+(\d+\.\d+)", rest)
            if m:
                ver = m.group(1)
                val = f"@lumen {ver}"
                tokens.append(Token(TokenType.VERSION, val, line_num, col))
                advance = 6 + m.end()
                col += advance
                i += advance
                continue
            else:
                tokens.append(Token(TokenType.AT, "@", line_num, col))
                i += 1
                col += 1
                continue

        # @ sin "lumen"
        if ch == "@":
            tokens.append(Token(TokenType.AT, "@", line_num, col))
            i += 1
            col += 1
            continue

        # Símbolos de moneda: $, €, £
        if ch in CURRENCY_SYMBOLS:
            result = _lex_money(content, i, line_num, col)
            if isinstance(result, LexError):
                return result
            tok, advance = result
            tokens.append(tok)
            i += advance
            col += advance
            continue

        # Números
        if ch.isdigit() or (ch == "." and i + 1 < n and content[i + 1].isdigit()):
            result = _lex_number_or_time(content, i, line_num, col)
            if isinstance(result, LexError):
                return result
            tok, advance = result
            tokens.append(tok)
            i += advance
            col += advance
            continue

        # Strings
        if ch == '"':
            str_result: Union[tuple[list[Token], int], LexError] = _lex_string(content, i, line_num, col)
            if isinstance(str_result, LexError):
                return str_result
            tok_list, advance = str_result
            tokens.extend(tok_list)
            i += advance
            col += advance
            continue

        # Identificadores y keywords
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (content[j].isalnum() or content[j] == "_"):
                j += 1
            word = content[i:j]
            ttype = KEYWORDS.get(word, TokenType.IDENTIFIER)
            tokens.append(Token(ttype, word, line_num, col))
            advance = j - i
            i += advance
            col += advance
            continue

        # Operadores de dos caracteres
        two = content[i : i + 2]
        if two == "->":
            tokens.append(Token(TokenType.ARROW, "->", line_num, col))
            i += 2
            col += 2
            continue
        if two == "=>":
            tokens.append(Token(TokenType.FAT_ARROW, "=>", line_num, col))
            i += 2
            col += 2
            continue
        if two == ">=":
            tokens.append(Token(TokenType.GTE, ">=", line_num, col))
            i += 2
            col += 2
            continue
        if two == "<=":
            tokens.append(Token(TokenType.LTE, "<=", line_num, col))
            i += 2
            col += 2
            continue
        if two == "==":
            tokens.append(Token(TokenType.EQ, "==", line_num, col))
            i += 2
            col += 2
            continue
        if two == "!=":
            tokens.append(Token(TokenType.NEQ, "!=", line_num, col))
            i += 2
            col += 2
            continue

        # Operadores de un carácter
        single_ops: dict[str, TokenType] = {
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.STAR,
            "/": TokenType.SLASH,
            "|": TokenType.PIPE,
            ">": TokenType.GT,
            "<": TokenType.LT,
            "=": TokenType.ASSIGN,
            "?": TokenType.QUESTION,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            "[": TokenType.LBRACKET,
            "]": TokenType.RBRACKET,
            ",": TokenType.COMMA,
            ":": TokenType.COLON,
            ".": TokenType.DOT,
        }
        if ch in single_ops:
            tokens.append(Token(single_ops[ch], ch, line_num, col))
            i += 1
            col += 1
            continue

        # Carácter desconocido
        return LexError(
            message=f"Carácter inesperado: {ch!r}",
            line=line_num,
            col=col,
            code="LMN-0010",
        )

    return tokens


def _lex_number_or_time(
    content: str, i: int, line_num: int, col: int
) -> Union[tuple[Token, int], LexError]:
    """Lexea un número, posiblemente seguido de unidad de tiempo."""
    j = i
    n = len(content)

    # Parte entera
    while j < n and content[j].isdigit():
        j += 1

    # Parte decimal
    if j < n and content[j] == "." and j + 1 < n and content[j + 1].isdigit():
        j += 1
        while j < n and content[j].isdigit():
            j += 1

    num_str = content[i:j]

    # Verificar si viene una unidad de tiempo
    # Orden: "min" antes de "m" (si lo hubiera)
    for unit in TIME_UNITS:
        end = j + len(unit)
        if content[j:end] == unit:
            # Verificar que no sigue un alfanumérico (e.g., "mine")
            if end < n and (content[end].isalnum() or content[end] == "_"):
                continue
            val = num_str + unit
            return Token(TokenType.TIME_LITERAL, val, line_num, col), end - i

    return Token(TokenType.NUMBER, num_str, line_num, col), j - i


def _lex_money(
    content: str, i: int, line_num: int, col: int
) -> Union[tuple[Token, int], LexError]:
    """Lexea un literal de dinero: símbolo número [CÓDIGO]."""
    symbol = content[i]
    j = i + 1
    n = len(content)

    # Debe seguir un número
    if j >= n or not (content[j].isdigit() or content[j] == "."):
        # No es un money literal; tratar símbolo como carácter desconocido
        return LexError(
            message=f"Se esperaba número después de símbolo de moneda {symbol!r}",
            line=line_num,
            col=col,
            code="LMN-0010",
        )

    # Parte entera
    while j < n and content[j].isdigit():
        j += 1

    # Parte decimal
    if j < n and content[j] == "." and j + 1 < n and content[j + 1].isdigit():
        j += 1
        while j < n and content[j].isdigit():
            j += 1

    num_str = content[i + 1 : j]

    # Código de moneda opcional (3 mayúsculas)
    currency_code = ""
    if j < n and content[j] == " ":
        k = j + 1
        end_k = k + 3
        if end_k <= n and content[k:end_k].isupper() and content[k:end_k].isalpha():
            # Verificar que no sigue más letras
            if end_k >= n or not (content[end_k].isalpha() or content[end_k] == "_"):
                currency_code = content[k:end_k]
                j = end_k

    val = f"{symbol}{num_str}"
    if currency_code:
        val = f"{symbol}{num_str} {currency_code}"

    return Token(TokenType.MONEY_LITERAL, val, line_num, col), j - i


def _lex_string(
    content: str, i: int, line_num: int, col: int
) -> Union[tuple[list[Token], int], LexError]:
    """Lexea un string, posiblemente con interpolaciones ${...}."""
    tokens: list[Token] = []
    j = i + 1  # saltar la comilla inicial
    n = len(content)
    current_str = ""
    str_start_col = col

    while j < n:
        ch = content[j]

        if ch == "\\":
            # Escape sequence
            if j + 1 < n:
                escaped = content[j + 1]
                current_str += "\\" + escaped
                j += 2
            else:
                return LexError(
                    message="Escape sequence incompleto al final de string",
                    line=line_num,
                    col=col + (j - i),
                    code="LMN-0010",
                )
            continue

        if ch == '"':
            # Fin del string
            if current_str or not tokens:
                tokens.append(
                    Token(TokenType.STRING, current_str, line_num, str_start_col)
                )
            j += 1
            return tokens, j - i

        if content[j : j + 2] == "${":
            # Inicio de interpolación
            if current_str:
                tokens.append(
                    Token(TokenType.STRING, current_str, line_num, str_start_col)
                )
                current_str = ""
            tokens.append(
                Token(TokenType.INTERP_START, "${", line_num, col + (j - i))
            )
            j += 2
            # Lexear hasta el } de cierre (nivel 1)
            brace_depth = 1
            interp_content = ""
            interp_start = j
            while j < n and brace_depth > 0:
                if content[j] == "{":
                    brace_depth += 1
                    interp_content += "{"
                elif content[j] == "}":
                    brace_depth -= 1
                    if brace_depth > 0:
                        interp_content += "}"
                else:
                    interp_content += content[j]
                j += 1

            if brace_depth > 0:
                return LexError(
                    message="Interpolación sin cerrar en string",
                    line=line_num,
                    col=col,
                    code="LMN-0010",
                )

            # Tokenizar el contenido de la interpolación
            interp_tokens = _tokenize_line(interp_content, line_num, col + (interp_start - i))
            if isinstance(interp_tokens, LexError):
                return interp_tokens
            tokens.extend(interp_tokens)

            tokens.append(
                Token(TokenType.INTERP_END, "}", line_num, col + (j - i) - 1)
            )
            str_start_col = col + (j - i)
            continue

        current_str += ch
        j += 1

    return LexError(
        message="String sin cerrar al final de línea",
        line=line_num,
        col=col,
        code="LMN-0010",
    )
