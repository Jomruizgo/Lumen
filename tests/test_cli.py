"""Tests para el CLI de Lumen usando CliRunner de typer."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lumen.cli import app

runner = CliRunner()

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
HELLO = str(EXAMPLES_DIR / "01_hello.lumen")
FUNCTION = str(EXAMPLES_DIR / "02_function.lumen")


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------

def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output or "Lumen" in result.output


# ---------------------------------------------------------------------------
# run --check-only
# ---------------------------------------------------------------------------

def test_run_check_only_hello():
    result = runner.invoke(app, ["run", "--check-only", HELLO])
    assert result.exit_code == 0
    assert "OK" in result.output or "compila" in result.output


def test_run_check_only_function():
    result = runner.invoke(app, ["run", "--check-only", FUNCTION])
    assert result.exit_code == 0


def test_run_check_only_all_examples():
    for lumen_file in sorted(EXAMPLES_DIR.glob("*.lumen")):
        result = runner.invoke(app, ["run", "--check-only", str(lumen_file)])
        assert result.exit_code == 0, f"{lumen_file.name} failed: {result.output}{result.stderr if hasattr(result, 'stderr') else ''}"


def test_run_check_only_nonexistent_file():
    result = runner.invoke(app, ["run", "--check-only", "does_not_exist.lumen"])
    assert result.exit_code != 0
    assert "no encontrado" in result.output.lower() or "error" in result.output.lower()


def test_run_check_only_invalid_syntax():
    with tempfile.NamedTemporaryFile(suffix=".lumen", mode="w", delete=False, encoding="utf-8") as f:
        f.write("this is @#$ invalid lumen syntax !!!")
        fname = f.name
    try:
        result = runner.invoke(app, ["run", "--check-only", fname])
        assert result.exit_code != 0
    finally:
        os.unlink(fname)


# ---------------------------------------------------------------------------
# run (full execution)
# ---------------------------------------------------------------------------

def test_run_hello_world():
    result = runner.invoke(app, ["run", HELLO])
    assert result.exit_code == 0


def test_run_nonexistent_file_errors():
    result = runner.invoke(app, ["run", "missing.lumen"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# run --dry-run
# ---------------------------------------------------------------------------

def test_run_dry_run():
    result = runner.invoke(app, ["run", "--dry-run", HELLO])
    assert result.exit_code == 0


def test_run_dry_run_nonexistent():
    result = runner.invoke(app, ["run", "--dry-run", "missing.lumen"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# fmt
# ---------------------------------------------------------------------------

def test_fmt_check_on_formatted_file():
    result = runner.invoke(app, ["fmt", "--check", HELLO])
    assert result.exit_code in (0, 1)


def test_fmt_formats_file(tmp_path: Path):
    source = 'version: "1.0"\nprint("hello")\n'
    lumen_file = tmp_path / "test.lumen"
    lumen_file.write_text(source, encoding="utf-8")
    result = runner.invoke(app, ["fmt", str(lumen_file)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_fmt_nonexistent_file():
    result = runner.invoke(app, ["fmt", "missing.lumen"])
    assert result.exit_code != 0


def test_fmt_check_nonexistent_file():
    result = runner.invoke(app, ["fmt", "--check", "missing.lumen"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# explain
# ---------------------------------------------------------------------------

def test_explain_hello():
    result = runner.invoke(app, ["explain", HELLO])
    assert result.exit_code == 0


def test_explain_nonexistent():
    result = runner.invoke(app, ["explain", "missing.lumen"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# agent subcommands (smoke tests — sin proceso real)
# ---------------------------------------------------------------------------

def test_agent_start_missing_file():
    result = runner.invoke(app, ["agent", "start", "myagent", "--file", "missing.lumen"])
    assert result.exit_code != 0


def test_agent_status_unknown():
    result = runner.invoke(app, ["agent", "status", "nonexistent_agent"])
    # Puede dar error o mostrar estado "unknown"
    assert result.exit_code in (0, 1)


def test_agent_logs_unknown():
    result = runner.invoke(app, ["agent", "logs", "nonexistent_agent"])
    assert result.exit_code in (0, 1)


def test_agent_stop_unknown():
    result = runner.invoke(app, ["agent", "stop", "nonexistent_agent"])
    assert result.exit_code in (0, 1)
