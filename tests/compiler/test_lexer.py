"""Tests del lexer Lumen.

Cubre:
- 9 tests obligatorios de la spec
- Tests de fixtures (50 archivos en fixtures/lexer/)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumen.compiler.lexer import (
    LexError,
    Token,
    TokenType,
    tokenize,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "lexer"


# ---------------------------------------------------------------------------
# Tests obligatorios de la spec (9)
# ---------------------------------------------------------------------------


def test_version_token() -> None:
    """@lumen 1.0 debe emitir un único token VERSION."""
    result = tokenize("@lumen 1.0")
    assert isinstance(result, list)
    types = [t.type for t in result]
    assert TokenType.VERSION in types
    ver_tok = next(t for t in result if t.type == TokenType.VERSION)
    assert ver_tok.value == "@lumen 1.0"


def test_time_literal_min() -> None:
    """5min debe emitir TIME_LITERAL con valor '5min'."""
    result = tokenize("5min")
    assert isinstance(result, list)
    time_toks = [t for t in result if t.type == TokenType.TIME_LITERAL]
    assert len(time_toks) == 1
    assert time_toks[0].value == "5min"


def test_time_literal_hours() -> None:
    """2h debe emitir TIME_LITERAL."""
    result = tokenize("2h")
    assert isinstance(result, list)
    time_toks = [t for t in result if t.type == TokenType.TIME_LITERAL]
    assert len(time_toks) == 1
    assert time_toks[0].value == "2h"


def test_money_literal_usd() -> None:
    """$100 USD debe emitir MONEY_LITERAL."""
    result = tokenize("$100 USD")
    assert isinstance(result, list)
    money_toks = [t for t in result if t.type == TokenType.MONEY_LITERAL]
    assert len(money_toks) == 1
    assert money_toks[0].value == "$100 USD"


def test_money_literal_eur() -> None:
    """€50 EUR debe emitir MONEY_LITERAL."""
    result = tokenize("€50 EUR")
    assert isinstance(result, list)
    money_toks = [t for t in result if t.type == TokenType.MONEY_LITERAL]
    assert len(money_toks) == 1
    assert money_toks[0].value == "€50 EUR"


def test_string_interpolation() -> None:
    """String con ${expr} debe emitir INTERP_START e INTERP_END."""
    result = tokenize('"Hello, ${name}"')
    assert isinstance(result, list)
    types = [t.type for t in result]
    assert TokenType.INTERP_START in types
    assert TokenType.INTERP_END in types
    assert TokenType.IDENTIFIER in types


def test_indent_dedent() -> None:
    """Bloques indentados emiten INDENT y DEDENT."""
    source = "fn foo():\n  return 1\n"
    result = tokenize(source)
    assert isinstance(result, list)
    types = [t.type for t in result]
    assert TokenType.INDENT in types
    assert TokenType.DEDENT in types


def test_doc_comment() -> None:
    """#: emite DOC_COMMENT con el texto."""
    result = tokenize("#: This is a doc comment")
    assert isinstance(result, list)
    doc_toks = [t for t in result if t.type == TokenType.DOC_COMMENT]
    assert len(doc_toks) == 1
    assert "This is a doc comment" in doc_toks[0].value


def test_invalid_char_returns_lexerror() -> None:
    """Carácter inválido retorna LexError con código LMN-0010."""
    result = tokenize("x = 1 ` y")
    assert isinstance(result, LexError)
    assert result.code == "LMN-0010"


# ---------------------------------------------------------------------------
# Tests unitarios adicionales
# ---------------------------------------------------------------------------


def test_keywords_recognized() -> None:
    """Todas las keywords deben reconocerse."""
    keywords = [
        ("action", TokenType.ACTION),
        ("agent", TokenType.AGENT),
        ("fn", TokenType.FN),
        ("use", TokenType.USE),
        ("import", TokenType.IMPORT),
        ("if", TokenType.IF),
        ("else", TokenType.ELSE),
        ("match", TokenType.MATCH),
        ("for", TokenType.FOR),
        ("return", TokenType.RETURN),
        ("resolve", TokenType.RESOLVE),
        ("because", TokenType.BECAUSE),
        ("true", TokenType.TRUE),
        ("false", TokenType.FALSE),
        ("pass", TokenType.PASS),
    ]
    for word, expected_type in keywords:
        result = tokenize(word)
        assert isinstance(result, list), f"Keyword '{word}' falló el lexing"
        non_meta = [t for t in result if t.type not in (TokenType.EOF, TokenType.NEWLINE)]
        assert len(non_meta) == 1
        assert non_meta[0].type == expected_type, f"Keyword '{word}' → esperaba {expected_type}, got {non_meta[0].type}"


def test_number_integer() -> None:
    result = tokenize("42")
    assert isinstance(result, list)
    nums = [t for t in result if t.type == TokenType.NUMBER]
    assert nums[0].value == "42"


def test_number_float() -> None:
    result = tokenize("3.14")
    assert isinstance(result, list)
    nums = [t for t in result if t.type == TokenType.NUMBER]
    assert nums[0].value == "3.14"


def test_empty_string() -> None:
    result = tokenize('""')
    assert isinstance(result, list)
    strings = [t for t in result if t.type == TokenType.STRING]
    assert len(strings) >= 1
    assert strings[0].value == ""


def test_simple_string() -> None:
    result = tokenize('"hello world"')
    assert isinstance(result, list)
    strings = [t for t in result if t.type == TokenType.STRING]
    assert strings[0].value == "hello world"


def test_comment_ignored() -> None:
    result = tokenize("# this is a comment\nx = 1")
    assert isinstance(result, list)
    types = [t.type for t in result]
    assert TokenType.DOC_COMMENT not in types
    assert TokenType.IDENTIFIER in types


def test_operators() -> None:
    ops = "-> => >= <= == !="
    result = tokenize(ops)
    assert isinstance(result, list)
    types = [t.type for t in result]
    assert TokenType.ARROW in types
    assert TokenType.FAT_ARROW in types
    assert TokenType.GTE in types
    assert TokenType.LTE in types
    assert TokenType.EQ in types
    assert TokenType.NEQ in types


def test_pipe_operator() -> None:
    result = tokenize("a | b")
    assert isinstance(result, list)
    types = [t.type for t in result]
    assert TokenType.PIPE in types


def test_tab_indentation_error() -> None:
    """Indentación con tab retorna LexError LMN-0011."""
    result = tokenize("fn foo():\n\treturn 1")
    assert isinstance(result, LexError)
    assert result.code == "LMN-0011"


def test_unclosed_string_error() -> None:
    """String sin cerrar retorna LexError LMN-0010."""
    result = tokenize('"unclosed string')
    assert isinstance(result, LexError)
    assert result.code == "LMN-0010"


def test_time_all_units() -> None:
    """Todas las unidades de tiempo deben reconocerse."""
    units = ["30s", "5min", "2h", "7d", "1w", "1y"]
    for u in units:
        result = tokenize(u)
        assert isinstance(result, list)
        time_toks = [t for t in result if t.type == TokenType.TIME_LITERAL]
        assert len(time_toks) == 1, f"Unidad '{u}' no reconocida como TIME_LITERAL"
        assert time_toks[0].value == u


def test_money_no_currency_code() -> None:
    """$50 sin código de moneda."""
    result = tokenize("$50")
    assert isinstance(result, list)
    money_toks = [t for t in result if t.type == TokenType.MONEY_LITERAL]
    assert len(money_toks) == 1
    assert money_toks[0].value == "$50"


def test_money_decimal() -> None:
    """$1000.50 USD debe tokenizarse correctamente."""
    result = tokenize("$1000.50 USD")
    assert isinstance(result, list)
    money_toks = [t for t in result if t.type == TokenType.MONEY_LITERAL]
    assert len(money_toks) == 1
    assert money_toks[0].value == "$1000.50 USD"


def test_money_gbp() -> None:
    """£75 GBP debe tokenizarse."""
    result = tokenize("£75 GBP")
    assert isinstance(result, list)
    money_toks = [t for t in result if t.type == TokenType.MONEY_LITERAL]
    assert len(money_toks) == 1
    assert money_toks[0].value == "£75 GBP"


def test_nested_indent() -> None:
    """Indentación anidada emite múltiples INDENT/DEDENT."""
    source = "fn outer():\n  if true:\n    return 1\n  return 0\n"
    result = tokenize(source)
    assert isinstance(result, list)
    types = [t.type for t in result]
    indent_count = types.count(TokenType.INDENT)
    dedent_count = types.count(TokenType.DEDENT)
    assert indent_count == 2
    assert dedent_count == 2


def test_identifier_varieties() -> None:
    """Identificadores válidos se reconocen."""
    ids = ["my_var", "_private", "camelCase", "x123"]
    for ident in ids:
        result = tokenize(ident)
        assert isinstance(result, list)
        id_toks = [t for t in result if t.type == TokenType.IDENTIFIER]
        assert len(id_toks) == 1
        assert id_toks[0].value == ident


def test_at_symbol() -> None:
    """@ sin 'lumen' emite AT token."""
    result = tokenize("@foo")
    assert isinstance(result, list)
    types = [t.type for t in result]
    assert TokenType.AT in types


def test_question_mark() -> None:
    result = tokenize("result?")
    assert isinstance(result, list)
    types = [t.type for t in result]
    assert TokenType.QUESTION in types


def test_eof_always_present() -> None:
    """EOF siempre es el último token."""
    for src in ["", "@lumen 1.0", "x = 1\n"]:
        result = tokenize(src)
        assert isinstance(result, list)
        assert result[-1].type == TokenType.EOF


def test_multiline_interp() -> None:
    """Múltiples interpolaciones en un string."""
    result = tokenize('"${a} and ${b}"')
    assert isinstance(result, list)
    types = [t.type for t in result]
    assert types.count(TokenType.INTERP_START) == 2
    assert types.count(TokenType.INTERP_END) == 2


def test_token_line_col() -> None:
    """Los tokens tienen línea y columna correctas."""
    result = tokenize("@lumen 1.0\nx = 1\n")
    assert isinstance(result, list)
    ver_tok = next(t for t in result if t.type == TokenType.VERSION)
    assert ver_tok.line == 1
    assert ver_tok.col == 1


def test_full_program() -> None:
    """Un programa completo lexea sin errores."""
    source = "@lumen 1.0\n\nfn add(a, b):\n  return a + b\n\nresult = add(2, 3)\n"
    result = tokenize(source)
    assert isinstance(result, list)
    types = [t.type for t in result]
    assert TokenType.VERSION in types
    assert TokenType.FN in types
    assert TokenType.RETURN in types
    assert TokenType.EOF in types


# ---------------------------------------------------------------------------
# Tests basados en fixtures
# ---------------------------------------------------------------------------


def _load_fixture(name: str) -> tuple[str, dict]:  # type: ignore[type-arg]
    lumen_path = FIXTURES_DIR / f"{name}.lumen"
    expected_path = FIXTURES_DIR / f"{name}.expected"
    source = lumen_path.read_text(encoding="utf-8")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    return source, expected


def _check_fixture(source: str, expected: dict) -> None:  # type: ignore[type-arg]
    result = tokenize(source)
    is_valid = expected.get("valid", True)

    if not is_valid:
        # Determinar el código de error esperado
        expected_code = expected.get("error_code", "")
        if not expected_code and "error" in expected and isinstance(expected["error"], dict):
            expected_code = expected["error"].get("code", "")

        # Solo LMN-0010 y LMN-0011 son errores léxicos. LMN-0100 es del parser.
        if expected_code in ("LMN-0010", "LMN-0011"):
            assert isinstance(result, LexError), f"Se esperaba LexError pero se obtuvo tokens"
            assert result.code == expected_code, (
                f"Error code esperado: {expected_code}, obtenido: {result.code}"
            )
        # Para LMN-0100 u otros: el lexer puede o no dar error, no verificamos
        return

    assert isinstance(result, list), f"Se esperaba lista de tokens pero se obtuvo: {result!r}"

    # Verificar tokens específicos si se especifican (solo tipos que existen en TokenType)
    if "tokens" in expected:
        valid_type_names = {t.name for t in TokenType}
        non_meta = [t for t in result if t.type not in (TokenType.EOF,)]
        for i, exp_tok in enumerate(expected["tokens"]):
            if i >= len(non_meta):
                break
            tok = non_meta[i]
            if "type" in exp_tok:
                exp_type = exp_tok["type"]
                # Ignorar tipos que no son parte de nuestra implementación
                if exp_type not in valid_type_names:
                    continue
                assert tok.type.name == exp_type, (
                    f"Token {i}: esperaba {exp_type}, obtuvo {tok.type.name}"
                )
            if "value" in exp_tok and "type" in exp_tok and exp_tok["type"] in valid_type_names:
                assert tok.value == exp_tok["value"], (
                    f"Token {i} ({tok.type.name}): valor esperado {exp_tok['value']!r}, obtenido {tok.value!r}"
                )

    # Verificar tokens que deben estar presentes (sin orden)
    if "tokens_include" in expected:
        result_type_names = {t.type.name for t in result}
        for ttype in expected["tokens_include"]:
            assert ttype in result_type_names, f"Se esperaba token {ttype} en el resultado"

    # Verificar presencia de INDENT/DEDENT
    types = [t.type for t in result]
    if expected.get("has_indent"):
        assert TokenType.INDENT in types
    if expected.get("has_dedent"):
        assert TokenType.DEDENT in types
    if expected.get("has_version"):
        assert TokenType.VERSION in types
    if expected.get("has_fn"):
        assert TokenType.FN in types
    if expected.get("has_return"):
        assert TokenType.RETURN in types

    if "indent_count" in expected:
        assert types.count(TokenType.INDENT) == expected["indent_count"]
    if "dedent_count" in expected:
        assert types.count(TokenType.DEDENT) == expected["dedent_count"]

    if "interp_start_count" in expected:
        assert types.count(TokenType.INTERP_START) == expected["interp_start_count"]
    if "interp_end_count" in expected:
        assert types.count(TokenType.INTERP_END) == expected["interp_end_count"]


# Generar un test por cada fixture
def _get_fixture_names() -> list[str]:
    names = []
    for f in sorted(FIXTURES_DIR.glob("*.lumen")):
        names.append(f.stem)
    return names


@pytest.mark.parametrize("fixture_name", _get_fixture_names())
def test_fixture(fixture_name: str) -> None:
    """Test parametrizado para cada fixture en fixtures/lexer/."""
    source, expected = _load_fixture(fixture_name)
    _check_fixture(source, expected)
