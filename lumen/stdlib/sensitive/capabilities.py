"""Capacidades sensitive.*: transferencias, borrado permanente, deploys."""

from __future__ import annotations

import uuid
from typing import Any

from lumen.stdlib.base import (
    Capability,
    CapabilityDescription,
    ExecutionContext,
    Result,
)


class SensitiveTransferMoney(Capability):
    name = "sensitive.transfer"
    mode = "safe"
    reversible = True
    requires_approval = True

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        from_acc: str = str(args.get("from", ""))
        to_acc: str = str(args.get("to", ""))
        amount: Any = args.get("amount")

        if not from_acc or not to_acc or amount is None:
            return Result.fail("transfer.money requiere 'from', 'to' y 'amount'")

        if context.dry_run:
            return Result.ok({
                "from": from_acc,
                "to": to_acc,
                "amount": amount,
                "status": "pending-dry-run",
            })

        if context.escalation_handler is not None:
            from lumen.runtime.escalation import EscalationRequest

            req = EscalationRequest(
                action={
                    "name": "transfer.money",
                    "amount": str(amount),
                    "from": from_acc,
                    "to": to_acc,
                    "reversible": "24h",
                },
                context=args.get("context", {}),
                timeout_seconds=300,
            )
            approval = await context.escalation_handler.request_approval(req)
            if not approval.approved:
                return Result.fail(f"Transferencia rechazada: {approval.reason}")

        action_id = str(uuid.uuid4())

        if context.undo_manager is not None:
            context.undo_manager.register(
                action_id=action_id,
                compensating_fn="transfer.money",
                compensating_args={"from": to_acc, "to": from_acc, "amount": amount},
                window_seconds=86400,
            )

        return Result.ok(
            {
                "from": from_acc,
                "to": to_acc,
                "amount": amount,
                "status": "completed",
                "transfer_id": action_id,
            },
            action_id=action_id,
        )

    async def undo(self, action_id: str, context: ExecutionContext) -> Result:
        if context.undo_manager is None:
            return Result.fail("UndoManager no disponible")
        result = context.undo_manager.undo(action_id)
        if result.success:
            return Result.ok({"undone": action_id})
        return Result.fail(result.message)

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="transfer.money(from: text, to: text, amount: Money) -> Pending<Reversible<Transfer>>",
            description="Transfiere dinero. Requiere aprobación humana. Reversible en 24h.",
            examples=["transfer.money(from=company_account, to=supplier.account, amount=$1000 USD)"],
        )


class SensitiveDeletePermanent(Capability):
    name = "sensitive.delete"
    mode = "safe"
    reversible = False
    requires_approval = True

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        path: str = str(args.get("path", ""))

        if not path:
            return Result.fail("delete.permanent requiere 'path'")

        if context.dry_run:
            return Result.ok({"path": path, "status": "pending-dry-run"})

        if context.escalation_handler is not None:
            from lumen.runtime.escalation import EscalationRequest

            req = EscalationRequest(
                action={
                    "name": "delete.permanent",
                    "path": path,
                    "reversible": False,
                    "warning": "Esta operación es IRREVERSIBLE",
                },
                context={},
                timeout_seconds=300,
            )
            approval = await context.escalation_handler.request_approval(req)
            if not approval.approved:
                return Result.fail(f"Borrado cancelado: {approval.reason}")

        import os
        from pathlib import Path as PPath

        target = PPath(path).expanduser()
        if not target.exists():
            return Result.fail(f"Ruta no encontrada: {path}")

        try:
            if target.is_file():
                os.unlink(target)
            else:
                import shutil
                shutil.rmtree(target)
            return Result.ok({"path": str(target), "status": "deleted"})
        except OSError as e:
            return Result.fail(f"Error al borrar {path}: {e}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="delete.permanent(path: Path) -> Pending<Irreversible<Deleted>>",
            description="Borra permanentemente. IRREVERSIBLE. Siempre requiere aprobación.",
            examples=["delete.permanent(path='/tmp/old_data')"],
        )


class SensitiveDeployProduction(Capability):
    name = "sensitive.deploy"
    mode = "safe"
    reversible = True
    requires_approval = True

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        system: str = str(args.get("system", ""))
        version: str = str(args.get("version", ""))
        webhook_url: str = str(args.get("webhook_url", ""))

        if not system or not version:
            return Result.fail("deploy.production requiere 'system' y 'version'")

        if context.dry_run:
            return Result.ok({"system": system, "version": version, "status": "pending-dry-run"})

        if context.escalation_handler is not None:
            from lumen.runtime.escalation import EscalationRequest

            req = EscalationRequest(
                action={
                    "name": "deploy.production",
                    "system": system,
                    "version": version,
                    "reversible": "1h",
                },
                context={},
                timeout_seconds=300,
            )
            approval = await context.escalation_handler.request_approval(req)
            if not approval.approved:
                return Result.fail(f"Deploy cancelado: {approval.reason}")

        action_id = str(uuid.uuid4())

        if webhook_url:
            import httpx

            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        webhook_url,
                        json={"system": system, "version": version, "action_id": action_id},
                        timeout=30.0,
                    )
            except Exception as e:
                return Result.fail(f"Error notificando webhook de deploy: {e}")

        return Result.ok(
            {"system": system, "version": version, "status": "deployed", "deploy_id": action_id},
            action_id=action_id,
        )

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="deploy.production(system: text, version: text) -> Pending<Reversible<Deployed>>",
            description="Deploy a producción. Requiere aprobación. Reversible en 1h.",
            examples=["deploy.production(system='api-service', version='v2.1.0')"],
        )
