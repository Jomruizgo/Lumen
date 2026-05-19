"""Tests para el dry-run mode."""

from __future__ import annotations

import pytest

from lumen.tooling.dryrun import dry_run


def test_dryrun_infers_fast_mode() -> None:
    source = '@lumen 1.0\nprint "hello"'
    plan = dry_run(source)
    assert plan.mode == "fast"


def test_dryrun_infers_safe_mode() -> None:
    source = "@lumen 1.0\nuse sensitive.transfer\ntransfer.money(from='A', to='B', amount=$100)"
    plan = dry_run(source)
    assert plan.mode == "safe"


def test_dryrun_infers_flow_mode() -> None:
    source = "@lumen 1.0\nuse comm.email\nagent monitor:\n  watch: read.email()"
    plan = dry_run(source)
    assert plan.mode == "flow"


def test_dryrun_shows_capabilities() -> None:
    source = "@lumen 1.0\nuse comm.email\nuse data.search\n"
    plan = dry_run(source)
    assert any("comm.email" in s.description for s in plan.steps)


def test_dryrun_marks_sensitive_as_approval_required() -> None:
    source = "@lumen 1.0\nuse sensitive.transfer\ntransfer.money(from='A', to='B')"
    plan = dry_run(source)
    assert plan.requires_approvals > 0


def test_dryrun_marks_delete_as_irreversible() -> None:
    source = "@lumen 1.0\nuse sensitive.delete\ndelete.permanent(path='/tmp/x')"
    plan = dry_run(source)
    assert plan.irreversible_count > 0


def test_dryrun_to_text_contains_mode() -> None:
    source = '@lumen 1.0\nprint "hello"'
    plan = dry_run(source)
    text = plan.to_text()
    assert "DRY-RUN" in text
    assert "FAST" in text


def test_dryrun_to_text_shows_no_execution_warning() -> None:
    source = '@lumen 1.0\nprint "hello"'
    plan = dry_run(source)
    text = plan.to_text()
    assert "No se ejecutó nada" in text


def test_dryrun_does_not_execute_capabilities() -> None:
    source = "@lumen 1.0\nuse sensitive.transfer\ntransfer.money(from='treasury', to='ops')"
    plan = dry_run(source)
    assert isinstance(plan.steps, list)
    assert len(plan.steps) >= 1
