"""Capacidades llm.*: ask, classify, extract."""

from __future__ import annotations

from typing import Any

from lumen.stdlib.base import (
    Capability,
    CapabilityDescription,
    ExecutionContext,
    Result,
)


class LLMAsk(Capability):
    name = "llm.ask"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        prompt: str = str(args.get("prompt", ""))
        ctx: dict[str, Any] = args.get("context", {})

        if not prompt:
            return Result.fail("llm.ask requiere 'prompt'")

        if context.dry_run:
            return Result.ok(f"[dry-run] LLM response to: {prompt[:50]}...")

        llm_client = getattr(context, "llm_client", None)
        if llm_client is None:
            return Result.fail("LLM client no configurado. Configure ~/.lumen/config.toml")

        full_prompt = prompt
        if ctx:
            import json
            full_prompt += f"\n\nContexto:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}"

        try:
            resolution = await llm_client.resolve(
                ambiguous=full_prompt,
                context=ctx,
                strategies=["ask"],
            )
            return Result.ok(resolution.value)
        except Exception as e:
            return Result.fail(f"Error llamando LLM: {e}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="llm.ask(prompt: text, context: Map = {}) -> Text",
            description="Hace una pregunta libre al LLM configurado y retorna la respuesta.",
            examples=['llm.ask(prompt="Resume este documento", context={"doc": content})'],
        )


class LLMClassify(Capability):
    name = "llm.classify"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        input_text: str = str(args.get("input", ""))
        categories: list[str] = args.get("categories", [])

        if not input_text:
            return Result.fail("llm.classify requiere 'input'")
        if not categories:
            return Result.fail("llm.classify requiere 'categories'")

        if context.dry_run:
            return Result.ok({
                "category": categories[0],
                "confidence": 0.5,
                "dry_run": True,
            })

        llm_client = getattr(context, "llm_client", None)
        if llm_client is None:
            return Result.fail("LLM client no configurado")

        prompt = (
            f"Clasifica el siguiente texto en una de estas categorías: {categories}\n\n"
            f"Texto: {input_text}\n\n"
            f'Responde SOLO con JSON: {{"category": "...", "confidence": 0.0}}'
        )

        try:
            resolution = await llm_client.resolve(
                ambiguous=input_text,
                context={"categories": categories},
                strategies=["classify"],
            )
            import json

            data = json.loads(resolution.value) if resolution.value.startswith("{") else {}
            return Result.ok({
                "category": data.get("category", categories[0]),
                "confidence": data.get("confidence", resolution.confidence),
            })
        except Exception as e:
            return Result.fail(f"Error en clasificación: {e}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="llm.classify(input: text, categories: List<text>) -> Confidence<Category>",
            description="Clasifica texto en una de las categorías dadas, con score de confianza.",
            examples=['llm.classify(input=email.subject, categories=["urgent", "normal", "spam"])'],
        )


class LLMExtract(Capability):
    name = "llm.extract"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        text: str = str(args.get("text", ""))
        schema: dict[str, Any] = args.get("schema", {})

        if not text:
            return Result.fail("llm.extract requiere 'text'")
        if not schema:
            return Result.fail("llm.extract requiere 'schema'")

        if context.dry_run:
            return Result.ok({k: f"[dry-run:{k}]" for k in schema})

        llm_client = getattr(context, "llm_client", None)
        if llm_client is None:
            return Result.fail("LLM client no configurado")

        import json

        prompt = (
            f"Extrae información del siguiente texto según este esquema JSON:\n"
            f"Esquema: {json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Texto:\n{text}\n\n"
            f"Responde SOLO con el JSON que sigue el esquema."
        )

        try:
            resolution = await llm_client.resolve(
                ambiguous=text,
                context={"schema": schema},
                strategies=["extract"],
            )
            try:
                extracted = json.loads(resolution.value)
            except (json.JSONDecodeError, ValueError):
                extracted = {"raw": resolution.value}
            return Result.ok(extracted)
        except Exception as e:
            return Result.fail(f"Error en extracción: {e}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="llm.extract(text: text, schema: Map) -> Structured",
            description="Extrae información estructurada de un texto según un esquema.",
            examples=[
                'llm.extract(text=email.body, schema={"amount": "number", "date": "text", "vendor": "text"})'
            ],
        )
