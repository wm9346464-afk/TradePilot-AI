"""Decimal-backed money value object."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from .currency import get_currency_meta, normalize_currency_code


class Money(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: str

    @field_validator("amount", mode="before")
    @classmethod
    def reject_float(cls, value: Any) -> Any:
        if isinstance(value, float):
            raise ValueError("Money.amount must not be a float; use Decimal or string")
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency_code(value)

    @property
    def exponent(self) -> int:
        return get_currency_meta(self.currency).exponent

    def quantized(self) -> "Money":
        meta = get_currency_meta(self.currency)
        return Money(
            amount=self.amount.quantize(meta.quantum, rounding=ROUND_HALF_UP),
            currency=self.currency,
        )

    def _same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot operate on different currencies: {self.currency} vs {other.currency}"
            )

    def __add__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency).quantized()

    def __sub__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency).quantized()

    def to_paypal_string(self) -> str:
        return f"{self.quantized().amount:.{self.exponent}f}"

    def format(self) -> str:
        value = self.quantized().amount
        return f"{self.currency} {value:,.{self.exponent}f}"


def money(amount: Decimal | int | str, currency: str) -> Money:
    if isinstance(amount, float):
        raise ValueError("Money.amount must not be a float; use Decimal or string")
    return Money(amount=Decimal(str(amount)), currency=currency).quantized()

