"""Example 14: Constants with audit annotations (because clauses).

Lumen's ``because`` annotation attaches rationale to assignments at the
language level. In Python we simulate this with explicit comments and a
helper that logs provenance.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def because(value: T, reason: str) -> T:
    """Attach an audit reason to a value (logged for traceability)."""
    logger.debug("REASON — %s: %r", reason, value)
    return value


def calculate_tax(amount: Decimal) -> Decimal:
    """Calculate Mexican IVA tax on amount.

    The constants carry audit provenance via ``because()``.
    """
    tax_rate = because(
        Decimal("0.16"),
        "IVA México 2026, ley vigente",
    )
    deadline = because(
        date(2026, 12, 31),
        "Cierre fiscal anual",
    )
    _ = deadline  # deadline used for scheduling, not shown here

    tax = amount * tax_rate
    return tax


def main() -> None:
    result = calculate_tax(Decimal("1000"))
    print(f"Tax: {result}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
