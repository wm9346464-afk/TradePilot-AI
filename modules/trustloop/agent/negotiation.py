"""Policy-constrained buyer/seller negotiation simulation."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..money import Money, money
from ..models import DealRun


class BuyerTerms(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_initial_payment: Money
    desired_credit_days: int
    accepted_currencies: list[str]


class SellerTerms(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_initial_payment: Money
    max_credit_days: int
    accepted_currencies: list[str]


class NegotiationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn: int
    actor: Literal["BUYER_AGENT", "SELLER_AGENT", "SYSTEM"]
    proposed_initial_payment: Money | None = None
    proposed_credit_days: int | None = None
    accepted: bool
    message: str


class NegotiationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agreed: bool
    currency: str
    final_initial_payment: Money | None = None
    final_credit_days: int | None = None
    turns: list[NegotiationTurn]
    summary: str


def negotiate(
    run: DealRun,
    *,
    max_turns: int = 5,
    buyer_max_initial_payment: str | int | None = None,
) -> NegotiationResult:
    """Run a bounded, deterministic negotiation."""
    if not run.plan or not run.plan.milestones:
        raise ValueError("A Trust Ladder plan is required before negotiation")
    if max_turns < 1:
        raise ValueError("max_turns must be positive")

    first = run.plan.milestones[0]
    currency = first.invoice_currency
    seller_min = first.amount
    buyer_max = money(
        buyer_max_initial_payment
        or max(first.amount.amount, Decimal("1000")),
        currency,
    )
    buyer = BuyerTerms(
        max_initial_payment=buyer_max,
        desired_credit_days=run.deal.requested_credit_days,
        accepted_currencies=[currency],
    )
    seller = SellerTerms(
        min_initial_payment=seller_min,
        max_credit_days=0,
        accepted_currencies=[currency],
    )

    buyer_offer_money = money(
        min(
            buyer.max_initial_payment.amount * Decimal("0.5"),
            seller.min_initial_payment.amount,
        ),
        currency,
    )
    turns: list[NegotiationTurn] = [
        NegotiationTurn(
            turn=1,
            actor="BUYER_AGENT",
            proposed_initial_payment=buyer_offer_money,
            proposed_credit_days=buyer.desired_credit_days,
            accepted=False,
            message=(
                f"Buyer offers {buyer_offer_money.format()} upfront and requests "
                f"{buyer.desired_credit_days} days of credit."
            ),
        )
    ]

    if buyer.max_initial_payment.amount < seller.min_initial_payment.amount:
        turns.append(
            NegotiationTurn(
                turn=2,
                actor="SELLER_AGENT",
                proposed_initial_payment=seller.min_initial_payment,
                proposed_credit_days=0,
                accepted=False,
                message="Seller rejects: buyer maximum is below the seller minimum.",
            )
        )
        return NegotiationResult(
            agreed=False,
            currency=currency,
            turns=turns,
            summary="No agreement: buyer and seller payment constraints do not overlap.",
        )

    seller_offer_money = money(
        max(buyer_offer_money.amount, seller.min_initial_payment.amount),
        currency,
    )
    credit_offer = min(buyer.desired_credit_days, seller.max_credit_days)
    turns.append(
        NegotiationTurn(
            turn=2,
            actor="SELLER_AGENT",
            proposed_initial_payment=seller_offer_money,
            proposed_credit_days=credit_offer,
            accepted=False,
            message=(
                f"Seller rejects unsecured credit and offers {seller_offer_money.format()} "
                f"upfront with {credit_offer} days of credit."
            ),
        )
    )
    if len(turns) < max_turns:
        turns.append(
            NegotiationTurn(
                turn=3,
                actor="BUYER_AGENT",
                proposed_initial_payment=seller_offer_money,
                proposed_credit_days=credit_offer,
                accepted=True,
                message=(
                    "Buyer accepts the staged milestone structure; credit is replaced "
                    "by verified milestone progression."
                ),
            )
        )
    agreed = (
        turns[-1].accepted
        and turns[-1].proposed_initial_payment is not None
        and turns[-1].proposed_initial_payment.amount
        <= buyer.max_initial_payment.amount
    )
    return NegotiationResult(
        agreed=agreed,
        currency=currency,
        final_initial_payment=turns[-1].proposed_initial_payment if agreed else None,
        final_credit_days=turns[-1].proposed_credit_days if agreed else None,
        turns=turns[:max_turns],
        summary=(
            f"Agreement: {turns[-1].proposed_initial_payment.format()} upfront, "
            f"{turns[-1].proposed_credit_days} days of credit, with milestone unlocks."
            if agreed
            else "No agreement within the allowed negotiation rounds."
        ),
    )

