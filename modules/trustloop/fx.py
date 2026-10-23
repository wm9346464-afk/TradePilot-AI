"""Timestamped FX snapshots for cross-currency settlement plans."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from .currency import normalize_currency_code
from .money import Money


class FxSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_currency: str
    quote_currency: str
    rate: Decimal
    source: str
    observed_at: datetime
    expires_at: datetime | None = None
    mode: Literal["LIVE", "DEMO_FIXTURE"] = "DEMO_FIXTURE"

    def is_valid(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return self.expires_at is None or current <= self.expires_at

    def convert(self, amount: Money) -> Money:
        if amount.currency != self.base_currency:
            raise ValueError(
                f"FX snapshot base {self.base_currency} cannot convert {amount.currency}"
            )
        if not self.is_valid():
            raise ValueError("FX snapshot has expired")
        return Money(
            amount=amount.amount * self.rate,
            currency=self.quote_currency,
        ).quantized()


class FxRateProvider(Protocol):
    def get_rate(self, base: str, quote: str) -> FxSnapshot:
        ...


class FixtureFxRateProvider:
    """Offline demo provider. Rates are fixtures, not live market quotes."""

    USD_RATES = {
        "USD": Decimal("1"),
        "CNY": Decimal("7.10"),
        "EUR": Decimal("0.92"),
        "GBP": Decimal("0.78"),
        "JPY": Decimal("150"),
        "HUF": Decimal("360"),
        "TWD": Decimal("32"),
        "HKD": Decimal("7.80"),
        "SGD": Decimal("1.34"),
        "AUD": Decimal("1.52"),
        "CAD": Decimal("1.38"),
        "BRL": Decimal("5.40"),
        "MYR": Decimal("4.70"),
    }

    def __init__(self, ttl_hours: int = 24) -> None:
        self.ttl = timedelta(hours=ttl_hours)

    def get_rate(self, base: str, quote: str) -> FxSnapshot:
        base_code = normalize_currency_code(base)
        quote_code = normalize_currency_code(quote)
        now = datetime.now(timezone.utc)
        if base_code == quote_code:
            rate = Decimal("1")
        else:
            rate = self.USD_RATES[quote_code] / self.USD_RATES[base_code]
        return FxSnapshot(
            base_currency=base_code,
            quote_currency=quote_code,
            rate=rate,
            source="TrustLoop DEMO_FIXTURE",
            observed_at=now,
            expires_at=now + self.ttl,
            mode="DEMO_FIXTURE",
        )

