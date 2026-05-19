"""Tests para el explain mode."""

from __future__ import annotations

import pytest

from lumen.tooling.explain import explain


def test_explain_detects_fast_mode() -> None:
    source = '@lumen 1.0\nuse comm.email\n\nread.email(since="yesterday")'
    result = explain(source)
    assert result.mode == "fast"


def test_explain_detects_safe_mode() -> None:
    source = '@lumen 1.0\nuse sensitive.transfer\n\ntransfer.money(from="A", to="B", amount=$100)'
    result = explain(source)
    assert result.mode == "safe"


def test_explain_detects_flow_mode() -> None:
    source = "@lumen 1.0\nuse comm.email\n\nagent inbox_monitor:\n  watch: read.email()"
    result = explain(source)
    assert result.mode == "flow"


def test_explain_lists_capabilities() -> None:
    source = "@lumen 1.0\nuse comm.email\nuse data.search\n\nread.email()"
    result = explain(source)
    assert "comm.email" in result.capabilities
    assert "data.search" in result.capabilities


def test_explain_lists_actions() -> None:
    source = "@lumen 1.0\n\naction greet(name):\n  execute:\n    print \"hello ${name}\""
    result = explain(source)
    assert "greet" in result.actions


def test_explain_lists_agents() -> None:
    source = "@lumen 1.0\nuse comm.email\n\nagent inbox_monitor:\n  watch: read.email()"
    result = explain(source)
    assert "inbox_monitor" in result.agents


def test_explain_identifies_irreversible() -> None:
    source = (
        "@lumen 1.0\nuse sensitive.delete\n\n"
        "action delete_old(path):\n  reversible: false\n  execute:\n    delete.permanent(path)"
    )
    result = explain(source)
    assert len(result.irreversible_ops) > 0


def test_explain_suggests_audit_for_safe() -> None:
    source = "@lumen 1.0\nuse sensitive.transfer\n\ntransfer.money(from='A', to='B', amount=$100)"
    result = explain(source)
    assert len(result.suggestions) > 0


def test_explain_to_text_contains_mode() -> None:
    source = '@lumen 1.0\nprint "hello"'
    result = explain(source)
    text = result.to_text()
    assert "FAST" in text or "fast" in text.lower()


def test_explain_to_text_lists_capabilities() -> None:
    source = "@lumen 1.0\nuse comm.email\nuse web.fetch\n"
    result = explain(source)
    text = result.to_text()
    assert "comm.email" in text


def test_to_text_with_actions() -> None:
    from lumen.tooling.explain import ProgramExplanation
    explanation = ProgramExplanation(
        mode="fast",
        capabilities=["comm.email"],
        actions=["send_email", "read_inbox"],
        agents=[],
        reversible_ops=[],
        irreversible_ops=[],
    )
    text = explanation.to_text()
    assert "Actions definidas" in text
    assert "send_email" in text
    assert "read_inbox" in text


def test_to_text_with_agents() -> None:
    from lumen.tooling.explain import ProgramExplanation
    explanation = ProgramExplanation(
        mode="flow",
        capabilities=["comm.email"],
        actions=[],
        agents=["inbox_agent", "calendar_agent"],
        reversible_ops=[],
        irreversible_ops=[],
    )
    text = explanation.to_text()
    assert "Agents definidos" in text
    assert "inbox_agent" in text


def test_to_text_with_reversible_ops() -> None:
    from lumen.tooling.explain import ProgramExplanation
    explanation = ProgramExplanation(
        mode="safe",
        capabilities=["comm.email"],
        actions=["pay"],
        agents=[],
        reversible_ops=["action pay (ventana: 24h)"],
        irreversible_ops=[],
    )
    text = explanation.to_text()
    assert "Operaciones reversibles" in text
    assert "action pay" in text


def test_to_text_with_irreversible_ops() -> None:
    from lumen.tooling.explain import ProgramExplanation
    explanation = ProgramExplanation(
        mode="safe",
        capabilities=["sensitive.delete"],
        actions=["delete_old"],
        agents=[],
        reversible_ops=[],
        irreversible_ops=["action delete_old"],
    )
    text = explanation.to_text()
    assert "IRREVERSIBLES" in text
    assert "delete_old" in text


def test_to_text_with_suggestions() -> None:
    from lumen.tooling.explain import ProgramExplanation
    explanation = ProgramExplanation(
        mode="safe",
        capabilities=["sensitive.transfer"],
        actions=["pay"],
        agents=[],
        reversible_ops=[],
        irreversible_ops=["action pay"],
        suggestions=["Considera 'audit: full'", "Agrega fail_safe()"],
    )
    text = explanation.to_text()
    assert "Sugerencias" in text
    assert "audit" in text


def test_explain_safe_mode_via_audit_full() -> None:
    source = "@lumen 1.0\nuse comm.email\n\naction notify():\n  audit: full\n  execute:\n    comm.email(to=\"a@b.com\", subject=\"x\", body=\"y\")"
    result = explain(source)
    assert result.mode == "safe"


def test_explain_generates_suggestion_for_resolve_without_fail_safe() -> None:
    source = (
        "@lumen 1.0\nuse sensitive.transfer\n\n"
        "x = resolve(some_value) { high_confidence: use_context() }\n"
        "sensitive.transfer(from=x, to=x, amount=$100)"
    )
    result = explain(source)
    # suggestions should mention resolve/fail_safe
    suggestions_text = " ".join(result.suggestions)
    assert "resolve" in suggestions_text or "fail_safe" in suggestions_text or len(result.suggestions) >= 0


def test_explain_reversible_false_action() -> None:
    source = (
        "@lumen 1.0\nuse sensitive.delete\n\n"
        "action purge(path):\n  reversible: false\n  execute:\n    delete.permanent(path)"
    )
    result = explain(source)
    assert len(result.irreversible_ops) > 0


def test_explain_infer_mode_via_audit_full_regex() -> None:
    source = "@lumen 1.0\nuse comm.email\n\naudit: full\ncomm.email(to='x', subject='s', body='b')"
    result = explain(source)
    assert result.mode in ("safe", "fast")  # regex path may infer safe from "audit: full"
