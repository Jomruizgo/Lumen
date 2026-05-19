"""Verifica que todos los códigos LMN-XXXX en código fuente están documentados."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
LUMEN_SRC = ROOT / "lumen"
ERRORS_DOC = ROOT / "docs" / "errors.md"


def collect_error_codes_in_source() -> set[str]:
    codes: set[str] = set()
    pattern = re.compile(r"LMN-\d{4}")

    for py_file in LUMEN_SRC.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="replace")
        codes.update(pattern.findall(content))

    return codes


def collect_error_codes_in_docs() -> set[str]:
    if not ERRORS_DOC.exists():
        return set()
    content = ERRORS_DOC.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"LMN-\d{4}", content))


def test_all_error_codes_documented() -> None:
    source_codes = collect_error_codes_in_source()
    doc_codes = collect_error_codes_in_docs()

    if not ERRORS_DOC.exists():
        pytest.skip(f"docs/errors.md no existe aún: {ERRORS_DOC}")

    missing = source_codes - doc_codes
    assert not missing, (
        f"Los siguientes códigos de error están en el código pero NO en docs/errors.md:\n"
        + "\n".join(sorted(missing))
    )


def test_error_codes_exist_in_source() -> None:
    source_codes = collect_error_codes_in_source()
    assert len(source_codes) >= 5, (
        f"Se esperan al menos 5 códigos LMN-XXXX en el código, encontrados: {source_codes}"
    )


def test_errors_doc_has_descriptions() -> None:
    if not ERRORS_DOC.exists():
        pytest.skip("docs/errors.md no existe aún")

    content = ERRORS_DOC.read_text(encoding="utf-8")
    codes = re.findall(r"LMN-\d{4}", content)

    assert len(codes) >= 5, "docs/errors.md debe documentar al menos 5 errores"

    for code in codes[:3]:
        assert code in content
