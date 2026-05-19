"""Escalation handlers: CLI interactivo y Webhook HTTP."""

from __future__ import annotations

import asyncio
import json
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse


@dataclass
class EscalationRequest:
    approval_id: str = field(default_factory=lambda: str(uuid4()))
    action: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300


@dataclass
class ApprovalResponse:
    approved: bool
    reason: str = ""
    approver: str = "human"


class EscalationTimeout(Exception):
    """LMN-0050 — Humano no respondió en tiempo."""

    code = "LMN-0050"


class EscalationHandler(ABC):
    @abstractmethod
    async def request_approval(self, request: EscalationRequest) -> ApprovalResponse:
        ...


class CLIEscalation(EscalationHandler):
    """Escalación interactiva por terminal."""

    def __init__(self, timeout_seconds: int = 300) -> None:
        self.timeout_seconds = timeout_seconds

    async def request_approval(self, request: EscalationRequest) -> ApprovalResponse:
        self._print_request(request)
        prompt = "\n  [a] Aprobar  [r] Rechazar  [d] Detalles  [c] Cancelar\n> "

        try:
            response = await asyncio.wait_for(
                self._read_input(prompt),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            print("\n[LUMEN] Timeout — operación cancelada", file=sys.stderr)
            raise EscalationTimeout(
                f"No se recibió respuesta en {self.timeout_seconds}s"
            )

        return self._parse_response(response, request)

    @staticmethod
    def _print_request(request: EscalationRequest) -> None:
        action = request.action
        print("\n[LUMEN] Aprobación requerida:")
        print(f"  Acción: {action.get('name', 'desconocida')}")
        if "amount" in action:
            print(f"  Monto: {action['amount']}")
        if "to" in action:
            print(f"  Destino: {action['to']}")
        if "reversible" in action:
            print(f"  Reversible: {action['reversible']}")
        if request.context:
            print(f"  Contexto: {request.context.get('description', '')}")

    @staticmethod
    async def _read_input(prompt: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input(prompt).strip().lower())

    @staticmethod
    def _parse_response(
        response: str, request: EscalationRequest
    ) -> ApprovalResponse:
        if response == "a":
            return ApprovalResponse(approved=True)
        if response in ("r", "c"):
            return ApprovalResponse(approved=False, reason="Rechazado por el usuario")
        if response == "d":
            print(f"\n[LUMEN] Detalles: {json.dumps(request.action, indent=2, ensure_ascii=False)}")
            return ApprovalResponse(approved=False, reason="Usuario solicitó detalles — reintente")
        return ApprovalResponse(approved=False, reason=f"Respuesta inválida: {response!r}")


class WebhookEscalation(EscalationHandler):
    """Escalación via webhook HTTP con callback local."""

    def __init__(self, webhook_url: str, timeout_seconds: int = 300) -> None:
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds

    async def request_approval(self, request: EscalationRequest) -> ApprovalResponse:
        callback_port = await self._find_free_port()
        callback_url = f"http://localhost:{callback_port}/approve/{request.approval_id}"

        payload = {
            "approval_id": request.approval_id,
            "action": request.action,
            "context": request.context,
            "callback_url": callback_url,
            "timeout_seconds": self.timeout_seconds,
        }

        response_future: asyncio.Future[ApprovalResponse] = asyncio.get_event_loop().create_future()
        server = await self._start_callback_server(
            callback_port, request.approval_id, response_future
        )

        try:
            async with httpx.AsyncClient() as client:
                await client.post(self.webhook_url, json=payload, timeout=10.0)

            return await asyncio.wait_for(
                response_future, timeout=float(self.timeout_seconds)
            )
        except asyncio.TimeoutError:
            raise EscalationTimeout(f"Webhook no respondió en {self.timeout_seconds}s")
        finally:
            server.cancel()

    @staticmethod
    async def _find_free_port() -> int:
        import socket

        with socket.socket() as s:
            s.bind(("", 0))
            return int(s.getsockname()[1])

    @staticmethod
    async def _start_callback_server(
        port: int,
        approval_id: str,
        future: asyncio.Future[ApprovalResponse],
    ) -> asyncio.Task[None]:
        app = FastAPI()

        @app.post(f"/approve/{approval_id}")
        async def approve(body: dict[str, Any]) -> JSONResponse:
            approved = bool(body.get("approved", False))
            reason = str(body.get("reason", ""))
            if not future.done():
                future.set_result(ApprovalResponse(approved=approved, reason=reason))
            return JSONResponse({"ok": True})

        @app.post(f"/reject/{approval_id}")
        async def reject(body: dict[str, Any]) -> JSONResponse:
            reason = str(body.get("reason", "Rechazado"))
            if not future.done():
                future.set_result(ApprovalResponse(approved=False, reason=reason))
            return JSONResponse({"ok": True})

        import uvicorn

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        server = uvicorn.Server(config)

        task = asyncio.create_task(server.serve())
        await asyncio.sleep(0.1)
        return task
