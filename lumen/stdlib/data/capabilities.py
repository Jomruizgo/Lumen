"""Capacidades data.*: file I/O, búsqueda semántica, extracción de entidades."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from lumen.stdlib.base import (
    Capability,
    CapabilityDescription,
    ExecutionContext,
    Result,
)


class DataReadFile(Capability):
    name = "data.read"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        path_str: str = args.get("path", "")
        if not path_str:
            return Result.fail("data.read requiere 'path'")

        path = Path(path_str).expanduser()
        if not path.exists():
            return Result.fail(f"Archivo no encontrado: {path}")

        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8", errors="replace")
            return Result.ok({"path": str(path), "content": content, "size": len(content)})
        except OSError as e:
            return Result.fail(f"Error leyendo {path}: {e}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="data.read(path: Path) -> Text | Bytes",
            description="Lee un archivo del filesystem de forma asíncrona.",
            examples=['data.read("~/Documents/report.pdf")', 'data.read("./config.json")'],
        )


class DataWriteFile(Capability):
    name = "data.write"
    mode = "fast"
    reversible = True
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        path_str: str = args.get("path", "")
        content: str = str(args.get("content", ""))

        if not path_str:
            return Result.fail("data.write requiere 'path'")

        path = Path(path_str).expanduser()

        if context.dry_run:
            return Result.ok({"path": str(path), "bytes": len(content), "dry_run": True})

        previously_existed = path.exists()
        previous_content: str | None = None
        if previously_existed:
            previous_content = await asyncio.to_thread(path.read_text, encoding="utf-8", errors="replace")

        try:
            await asyncio.to_thread(path.write_text, content, encoding="utf-8")

            if context.undo_manager is not None:
                compensating_args: dict[str, Any] = {"path": str(path)}
                if previously_existed and previous_content is not None:
                    compensating_args["restore_content"] = previous_content
                else:
                    compensating_args["delete"] = True

                import uuid
                action_id = str(uuid.uuid4())
                context.undo_manager.register(
                    action_id=action_id,
                    compensating_fn="data.write.undo",
                    compensating_args=compensating_args,
                    window_seconds=3600,
                )
                return Result.ok(
                    {"path": str(path), "bytes": len(content)},
                    action_id=action_id,
                )

            return Result.ok({"path": str(path), "bytes": len(content)})
        except OSError as e:
            return Result.fail(f"Error escribiendo {path}: {e}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="data.write(path: Path, content: Text) -> Reversible<Written>",
            description="Escribe contenido a un archivo. Registra compensating action para undo.",
            examples=['data.write("output.txt", "Hello World")'],
        )


class DataParseDocument(Capability):
    name = "data.parse"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        path_str: str = args.get("path", "")
        if not path_str:
            return Result.fail("data.parse requiere 'path'")

        path = Path(path_str).expanduser()
        suffix = path.suffix.lower()

        if not path.exists():
            return Result.fail(f"Archivo no encontrado: {path}")

        if suffix == ".md":
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            return Result.ok({"type": "markdown", "content": content, "path": str(path)})

        if suffix == ".json":
            import json

            text = await asyncio.to_thread(path.read_text, encoding="utf-8")
            try:
                data = json.loads(text)
                return Result.ok({"type": "json", "data": data, "path": str(path)})
            except json.JSONDecodeError as e:
                return Result.fail(f"JSON inválido: {e}")

        if suffix in (".txt", ".log", ".csv"):
            content = await asyncio.to_thread(path.read_text, encoding="utf-8", errors="replace")
            return Result.ok({"type": suffix[1:], "content": content, "path": str(path)})

        return Result.fail(f"Formato no soportado: {suffix}. Soportados: .md, .json, .txt, .csv")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="data.parse(path: Path) -> StructuredDoc",
            description="Parsea un documento (PDF, DOCX, MD, JSON) y retorna estructura.",
            examples=['data.parse("report.pdf")', 'data.parse("data.json")'],
        )


class DataSearchSemantic(Capability):
    name = "data.search"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        query: str = args.get("query", "")
        corpus: str = args.get("corpus", ".")

        if not query:
            return Result.fail("data.search requiere 'query'")

        corpus_path = Path(corpus).expanduser()
        if not corpus_path.exists():
            return Result.fail(f"Corpus no encontrado: {corpus_path}")

        results = await asyncio.to_thread(self._simple_search, query, corpus_path)
        return Result.ok({"query": query, "results": results})

    @staticmethod
    def _simple_search(query: str, corpus: Path) -> list[dict[str, Any]]:
        results = []
        query_lower = query.lower()
        for path in corpus.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in (".txt", ".md", ".py", ".lumen"):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                matches = content.lower().count(query_lower)
                if matches > 0:
                    results.append({
                        "path": str(path),
                        "relevance": min(1.0, matches / 10),
                        "snippet": content[:200],
                    })
            except OSError:
                continue
        return sorted(results, key=lambda r: r["relevance"], reverse=True)[:10]  # type: ignore[arg-type,return-value]

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="data.search(query: text, corpus: Path) -> List<Result>",
            description="Búsqueda semántica en un corpus de documentos.",
            examples=['data.search(query="contratos de 2026", corpus="~/Documents/")'],
        )


class DataExtractEntities(Capability):
    name = "data.extract"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        text: str = args.get("text", "")
        types: list[str] = args.get("types", ["PERSON", "ORG", "DATE", "MONEY"])

        if not text:
            return Result.fail("data.extract requiere 'text'")

        entities = await asyncio.to_thread(self._extract_simple, text, types)
        return Result.ok({"entities": entities, "count": len(entities)})

    @staticmethod
    def _extract_simple(text: str, types: list[str]) -> list[dict[str, Any]]:
        import re

        entities: list[dict[str, Any]] = []
        if "DATE" in types:
            for m in re.finditer(r"\d{4}-\d{2}-\d{2}", text):
                entities.append({"type": "DATE", "value": m.group(), "start": m.start()})
        if "MONEY" in types:
            for m in re.finditer(r"[$€£]\d+(?:[.,]\d+)?\s*(?:USD|EUR|GBP|MXN)?", text):
                entities.append({"type": "MONEY", "value": m.group(), "start": m.start()})
        if "EMAIL" in types:
            for m in re.finditer(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", text):
                entities.append({"type": "EMAIL", "value": m.group(), "start": m.start()})
        return sorted(entities, key=lambda e: e["start"])

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="data.extract(text: text, types: List<text>) -> List<Entity>",
            description="Extrae entidades nombradas de un texto.",
            examples=['data.extract(text="Pedro pagó $1000 el 2026-01-15", types=["PERSON", "MONEY", "DATE"])'],
        )
