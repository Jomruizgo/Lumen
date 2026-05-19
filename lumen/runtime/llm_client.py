"""Cliente LLM para resolución de ambigüedades via CLI configurable."""

from __future__ import annotations

import asyncio
import json
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx


def _get_config_path() -> Path:
    if platform.system() == "Windows":
        base = Path.home() / "AppData" / "Local"
        return base / "Lumen" / "config.toml"
    return Path.home() / ".lumen" / "config.toml"


def _get_cache_dir() -> Path:
    if platform.system() == "Windows":
        base = Path.home() / "AppData" / "Local"
        return base / "Lumen" / "cache"
    return Path.home() / ".lumen" / "cache"


@dataclass
class LLMConfig:
    command: str = "claude"
    args: list[str] = field(
        default_factory=lambda: ["--print", "--model", "claude-sonnet-4-6"]
    )
    timeout_seconds: int = 30
    max_retries: int = 2
    fallback_command: str = "echo"
    fallback_args: list[str] = field(default_factory=lambda: ["RESOLUTION_FAILED"])


@dataclass
class Resolution:
    value: str
    confidence: float
    strategy_used: str
    pending: bool = False


class LLMClient:
    """Cliente para resolución de ambigüedades via LLM CLI."""

    def __init__(
        self,
        config: LLMConfig | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.config = config or self._load_config()
        self._cache_dir = cache_dir or _get_cache_dir()
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_config() -> LLMConfig:
        config_path = _get_config_path()
        if not config_path.exists():
            return LLMConfig()
        try:
            import toml

            data = toml.load(config_path)
            resolver = data.get("resolver", {})
            return LLMConfig(
                command=resolver.get("command", "claude"),
                args=resolver.get("args", ["--print", "--model", "claude-sonnet-4-6"]),
                timeout_seconds=int(resolver.get("timeout_seconds", 30)),
                max_retries=int(resolver.get("max_retries", 2)),
            )
        except Exception:
            return LLMConfig()

    def _cache_key(self, ambiguous: str, context: dict[str, Any]) -> str:
        import hashlib

        payload = json.dumps({"ambiguous": ambiguous, "context": context}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _cache_get(self, key: str) -> Resolution | None:
        path = self._cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return Resolution(**data)
        except Exception:
            return None

    def _cache_set(self, key: str, resolution: Resolution) -> None:
        path = self._cache_dir / f"{key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "value": resolution.value,
                    "confidence": resolution.confidence,
                    "strategy_used": resolution.strategy_used,
                    "pending": resolution.pending,
                },
                f,
            )

    async def resolve(
        self,
        ambiguous: str,
        context: dict[str, Any],
        strategies: list[str],
    ) -> Resolution:
        cache_key = self._cache_key(ambiguous, context)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        prompt = self._build_prompt(ambiguous, context, strategies)

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._invoke_llm(prompt),
                    timeout=float(self.config.timeout_seconds),
                )
                resolution = self._parse_response(result, strategies)
                self._cache_set(cache_key, resolution)
                return resolution
            except asyncio.TimeoutError:
                if attempt == self.config.max_retries:
                    return await self._fallback(ambiguous)
                await asyncio.sleep(2**attempt)
            except Exception:
                if attempt == self.config.max_retries:
                    return await self._fallback(ambiguous)
                await asyncio.sleep(2**attempt)

        return await self._fallback(ambiguous)

    @staticmethod
    def _build_prompt(
        ambiguous: str, context: dict[str, Any], strategies: list[str]
    ) -> str:
        ctx_str = json.dumps(context, ensure_ascii=False, indent=2)
        return (
            f"Resuelve esta ambigüedad en un programa Lumen:\n"
            f"Valor ambiguo: {ambiguous!r}\n"
            f"Contexto: {ctx_str}\n"
            f"Estrategias disponibles: {strategies}\n\n"
            f"Responde SOLO con JSON: "
            f'{{\"value\": \"...\", \"confidence\": 0.0, \"strategy\": \"...\"}}'
        )

    async def _invoke_llm(self, prompt: str) -> str:
        cmd = [self.config.command] + self.config.args
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate(prompt.encode())
        return stdout.decode(errors="replace")

    @staticmethod
    def _parse_response(raw: str, strategies: list[str]) -> Resolution:
        import re

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return Resolution(value="", confidence=0.0, strategy_used="unknown")
        try:
            data = json.loads(match.group())
            return Resolution(
                value=str(data.get("value", "")),
                confidence=float(data.get("confidence", 0.0)),
                strategy_used=str(data.get("strategy", "unknown")),
            )
        except (json.JSONDecodeError, ValueError):
            return Resolution(value="", confidence=0.0, strategy_used="unknown")

    async def _fallback(self, ambiguous: str) -> Resolution:
        try:
            cmd = [self.config.fallback_command] + self.config.fallback_args
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
            )
            await process.communicate()
        except Exception:
            pass
        return Resolution(value="", confidence=0.0, strategy_used="fail_safe")
