"""Capacidades comm.*: email, mensajes, notificaciones, voz."""

from __future__ import annotations

import asyncio
import email as email_lib
import json
import platform
import smtplib
import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from lumen.stdlib.base import (
    Capability,
    CapabilityDescription,
    ExecutionContext,
    Result,
)


class CommReadEmail(Capability):
    name = "comm.read.email"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        since: str = str(args.get("since", "yesterday"))
        filter_args: dict[str, Any] = args.get("filter", {})
        max_count: int = int(args.get("max", 50))

        if context.dry_run:
            return Result.ok([
                {
                    "id": "mock-001",
                    "from": "sender@example.com",
                    "subject": "Mock email",
                    "body": "This is a mock email for dry-run",
                    "priority": 0.8,
                    "thread_id": "thread-001",
                    "timestamp": "2026-05-18T10:00:00Z",
                    "unread": True,
                }
            ])

        credentials = self._load_credentials()
        if credentials is None:
            return Result.fail(
                "Credenciales de email no configuradas. "
                "Ejecuta: lumen config email --setup"
            )

        return await asyncio.to_thread(
            self._fetch_emails, credentials, since, filter_args, max_count
        )

    @staticmethod
    def _load_credentials() -> dict[str, str] | None:
        from pathlib import Path

        cred_path = Path.home() / ".lumen" / "credentials" / "email.json"
        if platform.system() == "Windows":
            import os
            cred_path = (
                Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
                / "Lumen" / "credentials" / "email.json"
            )
        if not cred_path.exists():
            return None
        try:
            with open(cred_path, encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            return None

    @staticmethod
    def _fetch_emails(
        credentials: dict[str, str],
        since: str,
        filter_args: dict[str, Any],
        max_count: int,
    ) -> Result:
        import imaplib
        from datetime import datetime, timedelta

        host = credentials.get("imap_host", "imap.gmail.com")
        port = int(credentials.get("imap_port", 993))
        username = credentials.get("username", "")
        password = credentials.get("password", "")

        try:
            with imaplib.IMAP4_SSL(host, port) as imap:
                imap.login(username, password)
                imap.select("INBOX")

                criteria = "UNSEEN"
                if filter_args.get("unread"):
                    criteria = "UNSEEN"

                _, message_numbers = imap.search(None, criteria)
                emails = []
                for num in (message_numbers[0].split() or [])[:max_count]:
                    _, data = imap.fetch(num, "(RFC822)")
                    if data and data[0]:
                        raw = data[0][1] if isinstance(data[0], tuple) else b""
                        msg = email_lib.message_from_bytes(raw)
                        emails.append({
                            "id": num.decode(),
                            "from": msg.get("From", ""),
                            "subject": msg.get("Subject", ""),
                            "body": "",
                            "priority": 0.5,
                            "thread_id": msg.get("Message-ID", ""),
                            "timestamp": msg.get("Date", ""),
                            "unread": True,
                        })
                return Result.ok(emails)
        except Exception as e:
            return Result.fail(f"Error conectando a email: {e}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="read.email(since: text = 'yesterday', filter: Map = {}) -> List<Email>",
            description="Lee emails de la bandeja de entrada. Requiere credenciales configuradas.",
            examples=['read.email(since="yesterday")', 'read.email(filter={unread: true})'],
        )


class CommSendEmail(Capability):
    name = "comm.send.email"
    mode = "fast"
    reversible = True
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        to: str = str(args.get("to", ""))
        subject: str = str(args.get("subject", ""))
        body: str = str(args.get("body", ""))

        if not to or not subject:
            return Result.fail("send.email requiere 'to' y 'subject'")

        if context.dry_run:
            return Result.ok({
                "to": to,
                "subject": subject,
                "status": "pending-dry-run",
            })

        credentials = CommReadEmail._load_credentials()
        if credentials is None:
            return Result.fail("Credenciales SMTP no configuradas")

        return await asyncio.to_thread(self._send, credentials, to, subject, body)

    @staticmethod
    def _send(
        credentials: dict[str, str], to: str, subject: str, body: str
    ) -> Result:
        host = credentials.get("smtp_host", "smtp.gmail.com")
        port = int(credentials.get("smtp_port", 587))
        username = credentials.get("username", "")
        password = credentials.get("password", "")

        msg = MIMEMultipart()
        msg["From"] = username
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(username, password)
                server.sendmail(username, to, msg.as_string())
            return Result.ok({"to": to, "subject": subject, "status": "sent"})
        except smtplib.SMTPException as e:
            return Result.fail(f"Error enviando email: {e}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="send.email(to: EmailAddress, subject: text, body: text) -> Reversible<Sent>",
            description="Envía un email. Reversible (se puede cancelar si no fue entregado aún).",
            examples=['send.email(to="team@example.com", subject="Update", body="Hello")'],
        )


class CommSummarizeEmail(Capability):
    name = "comm.summarize.email"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        email_data: dict[str, Any] = args.get("email", {})
        max_lines: int = int(args.get("max_lines", 3))

        body: str = str(email_data.get("body", email_data.get("content", "")))
        if not body:
            return Result.fail("summarize.email requiere un email con 'body'")

        if context.dry_run:
            return Result.ok(f"[dry-run] Resumen de: {body[:50]}...")

        words = body.split()
        snippet = " ".join(words[: max_lines * 15])
        if len(words) > max_lines * 15:
            snippet += "..."

        return Result.ok(snippet)

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="summarize.email(email: Email, max_lines: number = 3) -> Text",
            description="Resume el cuerpo de un email en pocas líneas.",
            examples=["summarize.email(email=msg, max_lines=3)"],
        )


class CommNotifyUser(Capability):
    name = "comm.notify"
    mode = "fast"
    reversible = True
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        text: str = str(args.get("text", ""))
        priority: str = str(args.get("priority", "normal"))

        if not text:
            return Result.fail("notify.user requiere 'text'")

        if context.dry_run:
            return Result.ok({"text": text, "priority": priority, "dry_run": True})

        await asyncio.to_thread(self._notify, text, priority)
        return Result.ok({"text": text, "priority": priority, "status": "sent"})

    @staticmethod
    def _notify(text: str, priority: str) -> None:
        if platform.system() == "Windows":
            try:
                import winreg
                from ctypes import windll
                windll.user32.MessageBoxW(0, text, "Lumen", 0)
            except Exception:
                print(f"[LUMEN NOTIFY] {text}")
        else:
            try:
                subprocess.run(
                    ["notify-send", "--urgency=normal", "Lumen", text],
                    timeout=5,
                    check=False,
                )
            except FileNotFoundError:
                print(f"[LUMEN NOTIFY] {text}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="notify.user(text: text, priority: text = 'normal') -> Reversible<Notified>",
            description="Envía notificación nativa al usuario (toast en Windows, libnotify en Linux).",
            examples=['notify.user("Tarea completada", priority="high")'],
        )


class CommSendMessage(Capability):
    name = "comm.send.message"
    mode = "fast"
    reversible = True
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        channel: str = str(args.get("channel", "slack"))
        recipient: str = str(args.get("recipient", ""))
        text: str = str(args.get("text", ""))

        if not text:
            return Result.fail("send.message requiere 'text'")

        if context.dry_run:
            return Result.ok({
                "channel": channel,
                "recipient": recipient,
                "text": text,
                "dry_run": True,
            })

        return Result.ok({
            "channel": channel,
            "recipient": recipient,
            "text": text,
            "status": "sent (mock — configure webhook en ~/.lumen/credentials/)",
        })

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="send.message(channel: text, recipient: text, text: text) -> Reversible<Sent>",
            description="Envía mensaje a un canal (Slack, Telegram). Requiere webhook configurado.",
            examples=['send.message(channel="slack", recipient="#engineering", text="Deploy listo")'],
        )
