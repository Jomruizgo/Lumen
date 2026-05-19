"""Configuración global de pytest."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def examples_dir() -> Path:
    return Path(__file__).parent.parent / "examples"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return Path(__file__).parent / "compiler" / "fixtures"
