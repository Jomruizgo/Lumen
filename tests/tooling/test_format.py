"""Tests para el formatter de Lumen."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from lumen.tooling.format import check_format, format_source

# Directorio de ejemplos
EXAMPLES_DIR = Path(__file__).parents[2] / "examples"

# Los 15 archivos .lumen de ejemplo
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.lumen"))


def test_format_adds_trailing_newline() -> None:
    source = "@lumen 1.0"
    result = format_source(source)
    assert result.endswith("\n")


def test_format_idempotent() -> None:
    source = '@lumen 1.0\n\nfn add(a, b):\n  return a + b\n'
    formatted_once = format_source(source)
    formatted_twice = format_source(formatted_once)
    assert formatted_once == formatted_twice


def test_format_idempotent_100_programs() -> None:
    programs = [
        '@lumen 1.0\nprint "Hello, World"',
        "@lumen 1.0\n\nfn add(a, b):\n  return a + b\n\nresult = add(2, 3)",
        "@lumen 1.0\nuse comm.email\n\nemails = read.email(since='yesterday')",
        "@lumen 1.0\n\nif x > 0:\n  print 'positive'\nelse:\n  print 'negative'",
    ]
    for source in programs:
        f1 = format_source(source)
        f2 = format_source(f1)
        assert f1 == f2, f"Not idempotent for: {source!r}"


def test_format_normalizes_blank_lines() -> None:
    source = "@lumen 1.0\n\n\n\nprint 'hello'"
    result = format_source(source)
    assert "\n\n\n" not in result


def test_format_converts_single_to_double_quotes() -> None:
    source = "@lumen 1.0\nprint 'hello world'"
    result = format_source(source)
    assert '"hello world"' in result


def test_check_format_already_formatted() -> None:
    source = '@lumen 1.0\n\nprint "Hello"\n'
    assert check_format(source) == (format_source(source) == source)


def test_format_preserves_indentation() -> None:
    source = "@lumen 1.0\n\nfn greet(name):\n  print \"Hello ${name}\"\n"
    result = format_source(source)
    assert "  print" in result


def test_format_handles_empty_string() -> None:
    result = format_source("")
    assert isinstance(result, str)


def test_format_handles_only_newlines() -> None:
    result = format_source("\n\n\n")
    assert isinstance(result, str)
    assert result.endswith("\n")


# ---------------------------------------------------------------------------
# D.3 — Nuevos tests requeridos
# ---------------------------------------------------------------------------

def test_format_hello_world() -> None:
    """El formatter produce salida razonable para el ejemplo hello world."""
    source = '@lumen 1.0\n\nprint "Hello, World"\n'
    result = format_source(source)
    assert result.endswith("\n")
    assert "@lumen 1.0" in result
    assert "Hello, World" in result


@pytest.mark.parametrize("example_path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_idempotent(example_path: Path) -> None:
    """format(format(x)) == format(x) para cada uno de los 15 ejemplos."""
    source = example_path.read_text(encoding="utf-8")
    f1 = format_source(source)
    f2 = format_source(f1)
    assert f1 == f2, (
        f"El formatter no es idempotente para {example_path.name}.\n"
        f"Primera pasada:\n{f1!r}\n\nSegunda pasada:\n{f2!r}"
    )


def test_check_flag_exits_1_when_changed(tmp_path: Path) -> None:
    """lumen fmt --check <file> sale con código 1 si el archivo cambiaría."""
    # Archivo con indentación de tabs (no formateado)
    unformatted = tmp_path / "test.lumen"
    unformatted.write_text("@lumen 1.0\n\nfn foo():\n\treturn 1\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "lumen.cli", "fmt", "--check", str(unformatted)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        f"Se esperaba exit code 1, se obtuvo {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_check_flag_exits_0_when_clean(tmp_path: Path) -> None:
    """lumen fmt --check <file> sale con código 0 si el archivo ya está formateado."""
    from lumen.tooling.format import format_source as fmt

    # Crear un archivo ya correctamente formateado
    clean_source = fmt("@lumen 1.0\n\nfn foo():\n  return 1\n")
    clean_file = tmp_path / "clean.lumen"
    clean_file.write_text(clean_source, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "lumen.cli", "fmt", "--check", str(clean_file)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Se esperaba exit code 0, se obtuvo {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
