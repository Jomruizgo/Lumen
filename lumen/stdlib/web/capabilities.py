"""Capacidades web.*: fetch, post, serve webhook."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from lumen.stdlib.base import (
    Capability,
    CapabilityDescription,
    ExecutionContext,
    Result,
)


class WebFetch(Capability):
    name = "web.fetch"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        url: str = args.get("url", "")
        headers: dict[str, str] = args.get("headers", {})
        timeout: float = float(args.get("timeout", 30.0))

        if not url:
            return Result.fail("web.fetch requiere 'url'")

        if context.dry_run:
            return Result.ok({"url": url, "status": 200, "body": "[dry-run]"})

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=timeout)
                return Result.ok(
                    {
                        "status": response.status_code,
                        "body": response.text,
                        "headers": dict(response.headers),
                        "url": str(response.url),
                    }
                )
        except httpx.TimeoutException:
            return Result.fail(f"Timeout al conectar a {url}")
        except httpx.HTTPError as e:
            return Result.fail(f"Error HTTP: {e}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="web.fetch(url: Url, headers: Map<text,text> = {}) -> Response",
            description="Hace GET a una URL y retorna la respuesta.",
            examples=['web.fetch("https://api.github.com/users/octocat")'],
        )


class WebPost(Capability):
    name = "web.post"
    mode = "fast"
    reversible = True
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        url: str = args.get("url", "")
        body: Any = args.get("body", {})
        headers: dict[str, str] = args.get("headers", {})
        timeout: float = float(args.get("timeout", 30.0))

        if not url:
            return Result.fail("web.post requiere 'url'")

        if context.dry_run:
            return Result.ok({"url": url, "status": 200, "body": "[dry-run]"})

        try:
            async with httpx.AsyncClient() as client:
                if isinstance(body, dict):
                    response = await client.post(url, json=body, headers=headers, timeout=timeout)
                else:
                    response = await client.post(url, content=str(body).encode(), headers=headers, timeout=timeout)

                return Result.ok(
                    {
                        "status": response.status_code,
                        "body": response.text,
                        "headers": dict(response.headers),
                    }
                )
        except httpx.TimeoutException:
            return Result.fail(f"Timeout al conectar a {url}")
        except httpx.HTTPError as e:
            return Result.fail(f"Error HTTP: {e}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="web.post(url: Url, body: any, headers: Map<text,text> = {}) -> Reversible<Response>",
            description="Hace POST a una URL con body JSON o texto.",
            examples=['web.post("https://api.example.com/data", body={"key": "value"})'],
        )


class WebServeWebhook(Capability):
    name = "web.serve"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        port: int = int(args.get("port", 8080))
        handler: Any = args.get("handler")

        if context.dry_run:
            return Result.ok({"port": port, "status": "dry-run"})

        return Result.ok({"port": port, "status": "server started (placeholder)"})

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="web.serve(port: number, handler: fn) -> Server",
            description="Levanta un servidor webhook local en el puerto especificado.",
            examples=["web.serve(8080, handler=process_webhook)"],
        )
