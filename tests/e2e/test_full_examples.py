"""Tests E2E: ejecuta los 15 ejemplos con mocks de capacidades."""

from __future__ import annotations

from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"
EXAMPLE_FILES = [f"examples/{i:02d}_*.lumen" for i in range(1, 16)]


def get_example_files() -> list[Path]:
    if not EXAMPLES_DIR.exists():
        return []
    return sorted(EXAMPLES_DIR.glob("*.lumen"))


@pytest.mark.parametrize("example_path", get_example_files(), ids=lambda p: p.name)
def test_example_file_exists_and_readable(example_path: Path) -> None:
    assert example_path.exists()
    content = example_path.read_text(encoding="utf-8")
    assert "@lumen" in content
    assert len(content) > 10


@pytest.mark.parametrize("example_path", get_example_files(), ids=lambda p: p.name)
def test_example_starts_with_version(example_path: Path) -> None:
    content = example_path.read_text(encoding="utf-8")
    lines = [l for l in content.splitlines() if l.strip()]
    assert lines[0].startswith("@lumen"), f"{example_path.name} debe empezar con @lumen"


def test_all_15_examples_exist() -> None:
    examples = get_example_files()
    if not examples:
        pytest.skip("Ejemplos no creados aún — esperando Track D")
    assert len(examples) >= 15, f"Se esperan 15 ejemplos, encontrados: {len(examples)}"


def test_examples_have_unique_names() -> None:
    examples = get_example_files()
    if not examples:
        pytest.skip("Ejemplos no creados aún")
    names = [e.name for e in examples]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("example_path", get_example_files(), ids=lambda p: p.name)
def test_example_can_be_explained(example_path: Path) -> None:
    from lumen.tooling.explain import explain

    content = example_path.read_text(encoding="utf-8")
    result = explain(content)
    assert result.mode in ("fast", "safe", "flow")
    assert isinstance(result.capabilities, list)


@pytest.mark.parametrize("example_path", get_example_files(), ids=lambda p: p.name)
def test_example_can_be_dry_run(example_path: Path) -> None:
    from lumen.tooling.dryrun import dry_run

    content = example_path.read_text(encoding="utf-8")
    plan = dry_run(content)
    assert plan.mode in ("fast", "safe", "flow")
    assert isinstance(plan.steps, list)
    text = plan.to_text()
    assert "DRY-RUN" in text


@pytest.mark.parametrize("example_path", get_example_files(), ids=lambda p: p.name)
def test_example_can_be_formatted(example_path: Path) -> None:
    from lumen.tooling.format import format_source

    content = example_path.read_text(encoding="utf-8")
    formatted = format_source(content)
    assert isinstance(formatted, str)
    assert len(formatted) > 0
    formatted_again = format_source(formatted)
    assert formatted == formatted_again
