"""Tests para capabilities data.*."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumen.stdlib.base import ExecutionContext
from lumen.stdlib.data.capabilities import (
    DataExtractEntities,
    DataParseDocument,
    DataReadFile,
    DataSearchSemantic,
    DataWriteFile,
)


@pytest.fixture
def ctx() -> ExecutionContext:
    return ExecutionContext(mode="fast")


@pytest.fixture
def dry_ctx() -> ExecutionContext:
    return ExecutionContext(mode="fast", dry_run=True)


@pytest.mark.asyncio
async def test_read_file_exists(tmp_path: Path, ctx: ExecutionContext) -> None:
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, Lumen!", encoding="utf-8")

    cap = DataReadFile()
    result = await cap.execute({"path": str(test_file)}, ctx)
    assert result.success
    assert "Hello, Lumen!" in result.value["content"]


@pytest.mark.asyncio
async def test_read_file_not_found(ctx: ExecutionContext) -> None:
    cap = DataReadFile()
    result = await cap.execute({"path": "/nonexistent/file.txt"}, ctx)
    assert not result.success
    assert "no encontrado" in result.error.lower()


@pytest.mark.asyncio
async def test_read_file_no_path(ctx: ExecutionContext) -> None:
    cap = DataReadFile()
    result = await cap.execute({}, ctx)
    assert not result.success


@pytest.mark.asyncio
async def test_write_file(tmp_path: Path, ctx: ExecutionContext) -> None:
    target = tmp_path / "output.txt"
    cap = DataWriteFile()
    result = await cap.execute({"path": str(target), "content": "Written by Lumen"}, ctx)
    assert result.success
    assert target.read_text(encoding="utf-8") == "Written by Lumen"


@pytest.mark.asyncio
async def test_write_file_dry_run(tmp_path: Path, dry_ctx: ExecutionContext) -> None:
    target = tmp_path / "dry_output.txt"
    cap = DataWriteFile()
    result = await cap.execute({"path": str(target), "content": "Should not write"}, dry_ctx)
    assert result.success
    assert result.value.get("dry_run") is True
    assert not target.exists()


@pytest.mark.asyncio
async def test_parse_json(tmp_path: Path, ctx: ExecutionContext) -> None:
    test_file = tmp_path / "data.json"
    test_file.write_text('{"key": "value", "num": 42}', encoding="utf-8")

    cap = DataParseDocument()
    result = await cap.execute({"path": str(test_file)}, ctx)
    assert result.success
    assert result.value["type"] == "json"
    assert result.value["data"]["key"] == "value"


@pytest.mark.asyncio
async def test_parse_markdown(tmp_path: Path, ctx: ExecutionContext) -> None:
    test_file = tmp_path / "doc.md"
    test_file.write_text("# Title\n\nContent here.", encoding="utf-8")

    cap = DataParseDocument()
    result = await cap.execute({"path": str(test_file)}, ctx)
    assert result.success
    assert result.value["type"] == "markdown"


@pytest.mark.asyncio
async def test_parse_unsupported_format(tmp_path: Path, ctx: ExecutionContext) -> None:
    test_file = tmp_path / "data.xyz"
    test_file.write_text("unknown format", encoding="utf-8")

    cap = DataParseDocument()
    result = await cap.execute({"path": str(test_file)}, ctx)
    assert not result.success
    assert "no soportado" in result.error.lower()


@pytest.mark.asyncio
async def test_search_semantic(tmp_path: Path, ctx: ExecutionContext) -> None:
    (tmp_path / "doc1.txt").write_text("This is about Lumen language", encoding="utf-8")
    (tmp_path / "doc2.txt").write_text("Python programming guide", encoding="utf-8")

    cap = DataSearchSemantic()
    result = await cap.execute({"query": "Lumen", "corpus": str(tmp_path)}, ctx)
    assert result.success
    paths = [r["path"] for r in result.value["results"]]
    assert any("doc1" in p for p in paths)


@pytest.mark.asyncio
async def test_search_missing_query(ctx: ExecutionContext) -> None:
    cap = DataSearchSemantic()
    result = await cap.execute({"corpus": "."}, ctx)
    assert not result.success


@pytest.mark.asyncio
async def test_extract_dates(ctx: ExecutionContext) -> None:
    cap = DataExtractEntities()
    result = await cap.execute(
        {"text": "Reunión el 2026-05-20 para revisar los contratos", "types": ["DATE"]},
        ctx,
    )
    assert result.success
    entities = result.value["entities"]
    dates = [e for e in entities if e["type"] == "DATE"]
    assert any("2026-05-20" in e["value"] for e in dates)


@pytest.mark.asyncio
async def test_extract_money(ctx: ExecutionContext) -> None:
    cap = DataExtractEntities()
    result = await cap.execute(
        {"text": "Pago de $1000 USD al proveedor", "types": ["MONEY"]},
        ctx,
    )
    assert result.success
    entities = result.value["entities"]
    money = [e for e in entities if e["type"] == "MONEY"]
    assert len(money) >= 1


@pytest.mark.asyncio
async def test_extract_empty_text(ctx: ExecutionContext) -> None:
    cap = DataExtractEntities()
    result = await cap.execute({"text": "", "types": ["DATE"]}, ctx)
    assert not result.success
