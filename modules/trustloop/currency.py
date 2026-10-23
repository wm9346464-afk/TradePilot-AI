"""Currency metadata and PayPal-aware currency policy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


@dataclass(frozen=True)
class CurrencyMeta:
    code: str
    exponent: int
    paypal_supported: bool = True
    in_country_only: bool = False
    symbol: str = ""

    @property
    def quantum(self) -> Decimal:
        return Decimal("1").scaleb(-self.exponent)


CURRENCIES: dict[str, CurrencyMeta] = {
    "USD": CurrencyMeta("USD", 2, symbol="$"),
    "EUR": CurrencyMeta("EUR", 2, symbol="€"),
    "GBP": CurrencyMeta("GBP", 2, symbol="£"),
    "JPY": CurrencyMeta("JPY", 0, symbol="¥"),
    "HUF": CurrencyMeta("HUF", 0, symbol="Ft"),
    "TWD": CurrencyMeta("TWD", 0, symbol="NT$"),
    "CNY": CurrencyMeta("CNY", 2, in_country_only=True, symbol="¥"),
    "HKD": CurrencyMeta("HKD", 2, symbol="HK$"),
    "SGD": CurrencyMeta("SGD", 2, symbol="S$"),
    "AUD": CurrencyMeta("AUD", 2, symbol="A$"),
    "CAD": CurrencyMeta("CAD", 2, symbol="C$"),
    "BRL": CurrencyMeta("BRL", 2, in_country_only=True, symbol="R$"),
    "MYR": CurrencyMeta("MYR", 2, in_country_only=True, symbol="RM"),
}

CORE_CURRENCIES = (
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CNY",
    "HKD",
    "SGD",
    "AUD",
    "CAD",
)


def normalize_currency_code(value: str) -> str:
    code = str(value or "").strip().upper()
    if code not in CURRENCIES:
        raise ValueError(f"Unsupported ISO currency code: {code or '<empty>'}")
    return code


def get_currency_meta(value: str) -> CurrencyMeta:
    return CURRENCIES[normalize_currency_code(value)]


CurrencyStatus = Literal[
    "ALLOW",
    "REQUIRES_CONVERSION",
    "IN_COUNTRY_ONLY",
    "UNSUPPORTED",
    "INVALID_CURRENCY",
]


class CurrencyDecision(BaseModel):
    status: CurrencyStatus
    currency: str
    invoice_currency: str | None = None
    reason: str

    @property
    def allowed(self) -> bool:
        return self.status in {"ALLOW", "REQUIRES_CONVERSION"}


class CurrencyPolicy:
    """Validate PayPal currency eligibility before an invoice is created."""

    def __init__(self, fallback_currency: str = "USD") -> None:
        self.fallback_currency = normalize_currency_code(fallback_currency)

    def validate_invoice_currency(
        self,
        currency: str,
        merchant_supported: set[str] | frozenset[str] | tuple[str, ...],
        seller_country: str,
        buyer_country: str,
    ) -> CurrencyDecision:
        try:
            code = normalize_currency_code(currency)
        except ValueError as exc:
            return CurrencyDecision(
                status="INVALID_CURRENCY",
                currency=str(currency or ""),
                reason=str(exc),
            )

        meta = CURRENCIES[code]
        supported = {str(item).upper() for item in merchant_supported}
        if not meta.paypal_supported or code not in supported:
            return CurrencyDecision(
                status="UNSUPPORTED",
                currency=code,
                invoice_currency=self.fallback_currency,
                reason=(
                    f"{code} is not enabled for this PayPal merchant. "
                    f"Use {self.fallback_currency} or enable the currency in PayPal."
                ),
            )

        seller = str(seller_country or "").strip().upper()
        buyer = str(buyer_country or "").strip().upper()
        if meta.in_country_only and seller != buyer:
            return CurrencyDecision(
                status="IN_COUNTRY_ONLY",
                currency=code,
                invoice_currency=self.fallback_currency,
                reason=(
                    f"{code} is supported by PayPal for in-country accounts only. "
                    f"This cross-border case requires a settlement currency such as "
                    f"{self.fallback_currency} and an FX snapshot."
                ),
            )

        return CurrencyDecision(
            status="ALLOW",
            currency=code,
            invoice_currency=code,
            reason=f"{code} is allowed for this payment path.",
        )

