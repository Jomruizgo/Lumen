"""tests/test_docs_completeness.py

Suite de tests para docs/tests/docs_completeness.py.
Verifica que todos los códigos LMN-XXXX del código fuente estén en docs/errors.md.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

# Añade el repo root al path para poder importar desde docs/tests/
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "docs" / "tests"))

from docs_completeness import (  # noqa: E402
    check_completeness,
    find_codes_in_docs,
    find_codes_in_source,
)


class TestFindCodesInSource:
    """Tests para la función find_codes_in_source."""

    def test_finds_lmn_codes_in_py_files(self, tmp_path: Path) -> None:
        pkg = tmp_path / "lumen"
        pkg.mkdir()
        (pkg / "errors.py").write_text(
            'code = "LMN-0001"\nother = "LMN-0030"\n', encoding="utf-8"
        )
        codes = find_codes_in_source(pkg)
        assert "LMN-0001" in codes
        assert "LMN-0030" in codes

    def test_ignores_excluded_placeholder_codes(self, tmp_path: Path) -> None:
        pkg = tmp_path / "lumen"
        pkg.mkdir()
        (pkg / "pipeline.py").write_text(
            'code = getattr(err, "code", "LMN-0000")\n'
            'def __init__(self, message: str, code: str = "LMN-0099") -> None:\n',
            encoding="utf-8",
        )
        codes = find_codes_in_source(pkg)
        assert "LMN-0000" not in codes
        assert "LMN-0099" not in codes

    def test_scans_subdirectories_recursively(self, tmp_path: Path) -> None:
        pkg = tmp_path / "lumen"
        subpkg = pkg / "compiler"
        subpkg.mkdir(parents=True)
        (subpkg / "parser.py").write_text('code = "LMN-0010"\n', encoding="utf-8")
        codes = find_codes_in_source(pkg)
        assert "LMN-0010" in codes

    def test_no_codes_returns_empty_set(self, tmp_path: Path) -> None:
        pkg = tmp_path / "lumen"
        pkg.mkdir()
        (pkg / "clean.py").write_text("def foo(): pass\n", encoding="utf-8")
        codes = find_codes_in_source(pkg)
        assert codes == set()


class TestFindCodesInDocs:
    """Tests para la función find_codes_in_docs."""

    def test_finds_codes_in_markdown(self, tmp_path: Path) -> None:
        md = tmp_path / "errors.md"
        md.write_text(
            "## LMN-0001 — CapabilityNotDeclared\n## LMN-0010 — SyntaxError\n",
            encoding="utf-8",
        )
        codes = find_codes_in_docs(md)
        assert "LMN-0001" in codes
        assert "LMN-0010" in codes

    def test_finds_codes_in_table(self, tmp_path: Path) -> None:
        md = tmp_path / "errors.md"
        md.write_text(
            "| LMN-0030 | TypeMismatch | Compilador | Todos |\n",
            encoding="utf-8",
        )
        codes = find_codes_in_docs(md)
        assert "LMN-0030" in codes

    def test_empty_doc_returns_empty_set(self, tmp_path: Path) -> None:
        md = tmp_path / "errors.md"
        md.write_text("# Sin códigos aquí\n", encoding="utf-8")
        codes = find_codes_in_docs(md)
        assert codes == set()


class TestCheckCompleteness:
    """Tests de integración para check_completeness."""

    def test_all_documented_returns_empty_missing(self, tmp_path: Path) -> None:
        pkg = tmp_path / "lumen"
        pkg.mkdir()
        (pkg / "errors.py").write_text('code = "LMN-0001"\n', encoding="utf-8")

        md = tmp_path / "errors.md"
        md.write_text("## LMN-0001 — CapabilityNotDeclared\n", encoding="utf-8")

        source_codes, missing = check_completeness(
            lumen_root=pkg, errors_md=md
        )
        assert "LMN-0001" in source_codes
        assert missing == set()

    def test_undocumented_code_appears_in_missing(self, tmp_path: Path) -> None:
        pkg = tmp_path / "lumen"
        pkg.mkdir()
        (pkg / "errors.py").write_text(
            'code = "LMN-0001"\nother = "LMN-0099"\n', encoding="utf-8"
        )

        md = tmp_path / "errors.md"
        md.write_text("## LMN-0001 — CapabilityNotDeclared\n", encoding="utf-8")

        # LMN-0099 está en EXCLUDED_CODES, así que no debe aparecer como faltante
        source_codes, missing = check_completeness(
            lumen_root=pkg, errors_md=md
        )
        assert missing == set()

    def test_genuinely_missing_code_detected(self, tmp_path: Path) -> None:
        pkg = tmp_path / "lumen"
        pkg.mkdir()
        (pkg / "errors.py").write_text(
            'code = "LMN-0001"\nnew_code = "LMN-0042"\n', encoding="utf-8"
        )

        md = tmp_path / "errors.md"
        md.write_text("## LMN-0001 — CapabilityNotDeclared\n", encoding="utf-8")

        source_codes, missing = check_completeness(
            lumen_root=pkg, errors_md=md
        )
        assert "LMN-0042" in missing
        assert "LMN-0001" not in missing

    def test_missing_lumen_dir_raises(self, tmp_path: Path) -> None:
        md = tmp_path / "errors.md"
        md.write_text("", encoding="utf-8")
        with pytest.raises(FileNotFoundError, match="lumen/"):
            check_completeness(
                lumen_root=tmp_path / "nonexistent",
                errors_md=md,
            )

    def test_missing_errors_md_raises(self, tmp_path: Path) -> None:
        pkg = tmp_path / "lumen"
        pkg.mkdir()
        with pytest.raises(FileNotFoundError, match="errors.md"):
            check_completeness(
                lumen_root=pkg,
                errors_md=tmp_path / "nonexistent.md",
            )


class TestRealProject:
    """Prueba de integración contra el proyecto real."""

    def test_all_lmn_codes_are_documented(self) -> None:
        """Falla si hay códigos LMN en el código fuente sin entrada en docs/errors.md."""
        source_codes, missing = check_completeness()

        missing_list = sorted(missing)
        assert not missing_list, (
            f"Los siguientes códigos LMN existen en lumen/ pero NO están en docs/errors.md:\n"
            + "\n".join(f"  - {c}" for c in missing_list)
        )
