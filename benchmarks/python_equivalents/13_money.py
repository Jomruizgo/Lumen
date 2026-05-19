"""Example 13: Money literals with currency type safety.

Lumen has first-class money literals ($100 USD, EUR50 EUR) with
compile-time currency mismatch detection. In Python we simulate this
with a typed Money class.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Union


@dataclass(frozen=True)
class Money:
    """A monetary amount with an explicit currency."""

    amount: Decimal
    currency: str

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise TypeError(
                f"Cannot add {self.currency} and {other.currency}: "
                "currency mismatch (LMN-0030 TypeMismatch equivalent)"
            )
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __repr__(self) -> str:
        return f"${self.amount} {self.currency}"


def main() -> None:
    usd_amount = Money(Decimal("100"), "USD")  # $100 USD
    eur_amount = Money(Decimal("50"), "EUR")   # EUR50 EUR

    # Same-currency: valid
    total_usd = usd_amount + Money(Decimal("50"), "USD")
    print(f"Total USD: {total_usd}")

    # Cross-currency: runtime TypeError (compile-time in Lumen)
    # total_mixed = usd_amount + eur_amount  # raises TypeError


if __name__ == "__main__":
    main()
