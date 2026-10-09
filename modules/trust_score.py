#!/usr/bin/env python3
"""
TradePilot AI - Trust Score Module
New customer trust scoring system for commodity trading.

Evaluates new customer trustworthiness across 5 dimensions:
1. Contract Completeness (25 pts) - key clauses present
2. Payment History (25 pts) - payment track record
3. Market Stability (20 pts) - current market volatility
4. Company Info (15 pts) - company information completeness
5. Transaction Size (15 pts) - first deal size reasonableness

Score range: 0-100
Trust levels: High (80-100), Medium (50-79), Low (0-49)
"""

from typing import Optional


class TrustScoreResult:
    """Trust score result with breakdown and recommendations."""

    def __init__(self, total: int, level: str, dimensions: dict,
                 recommendations: list, lang: str = "zh"):
        self.total = total
        self.level = level
        self.dimensions = dimensions
        self.recommendations = recommendations
        self.lang = lang

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "level": self.level,
            "level_en": {"高": "High", "中": "Medium", "低": "Low"}.get(self.level, self.level),
            "dimensions": self.dimensions,
            "recommendations": self.recommendations,
        }


def calculate_trust_score(
    contract_issues_count: int = 0,
    contract_high_risk_count: int = 0,
    has_payment_history: bool = False,
    payment_on_time_rate: float = 1.0,
    market_volatility: str = "medium",
    company_name_provided: bool = True,
    company_contact_provided: bool = True,
    transaction_amount: float = 1000.0,
    customer_country: str = "unknown",
    lang: str = "zh",
) -> TrustScoreResult:
    """
    Calculate trust score for a new customer.

    Args:
        contract_issues_count: Number of issues found in contract review
        contract_high_risk_count: Number of high-severity issues
        has_payment_history: Whether customer has payment history
        payment_on_time_rate: On-time payment rate (0.0-1.0)
        market_volatility: "low", "medium", "high"
        company_name_provided: Whether company name is provided
        company_contact_provided: Whether contact info is provided
        transaction_amount: First transaction amount in USD
        customer_country: Customer country/region
        lang: Output language ("zh" or "en")

    Returns:
        TrustScoreResult with total score, level, dimension breakdown, and recommendations
    """
    dimensions = {}
    recommendations = []

    # 1. Contract Completeness (25 pts)
    contract_score = 25
    contract_score -= min(contract_issues_count * 2, 15)
    contract_score -= min(contract_high_risk_count * 5, 10)
    contract_score = max(0, contract_score)
    dimensions["contract"] = {
        "score": contract_score,
        "max": 25,
        "label": "合同完整性" if lang == "zh" else "Contract Completeness",
    }
    if contract_high_risk_count > 0:
        recommendations.append(
            f"合同存在{contract_high_risk_count}个高风险问题，建议在签署前解决。" if lang == "zh"
            else f"Contract has {contract_high_risk_count} high-risk issues, recommend resolving before signing."
        )

    # 2. Payment History (25 pts)
    if has_payment_history:
        payment_score = int(10 + payment_on_time_rate * 15)
        if payment_on_time_rate < 0.8:
            recommendations.append(
                "客户付款准时率较低，建议要求预付或使用PayPal担保交易。" if lang == "zh"
                else "Customer has low on-time payment rate, recommend upfront payment or PayPal protected transaction."
            )
    else:
        payment_score = 12  # Default for new customer with no history
        recommendations.append(
            "新客户无付款历史，建议首次交易使用PayPal样品费模式建立信任。" if lang == "zh"
            else "New customer with no payment history, recommend using PayPal sample fee mode for first transaction to build trust."
        )
    payment_score = max(0, min(25, payment_score))
    dimensions["payment"] = {
        "score": payment_score,
        "max": 25,
        "label": "付款历史" if lang == "zh" else "Payment History",
    }

    # 3. Market Stability (20 pts)
    volatility_scores = {"low": 20, "medium": 14, "high": 8}
    market_score = volatility_scores.get(market_volatility, 14)
    dimensions["market"] = {
        "score": market_score,
        "max": 20,
        "label": "行情稳定性" if lang == "zh" else "Market Stability",
    }
    if market_volatility == "high":
        recommendations.append(
            "当前市场波动较大，建议约定价格调整条款或分批交货。" if lang == "zh"
            else "High market volatility, recommend price adjustment clauses or split delivery."
        )

    # 4. Company Info (15 pts)
    info_score = 0
    if company_name_provided:
        info_score += 8
    if company_contact_provided:
        info_score += 7
    dimensions["company"] = {
        "score": info_score,
        "max": 15,
        "label": "公司信息" if lang == "zh" else "Company Info",
    }
    if not company_name_provided or not company_contact_provided:
        recommendations.append(
            "客户公司信息不完整，建议核实公司资质和联系方式。" if lang == "zh"
            else "Customer company information incomplete, recommend verifying company credentials and contact info."
        )

    # 5. Transaction Size (15 pts)
    if transaction_amount <= 0:
        size_score = 5
    elif transaction_amount <= 1000:
        size_score = 15  # Small first deal is low risk
    elif transaction_amount <= 10000:
        size_score = 12
    elif transaction_amount <= 50000:
        size_score = 8
    else:
        size_score = 5
        recommendations.append(
            "首次交易金额较大，建议分期付款或使用信用证降低风险。" if lang == "zh"
            else "Large first transaction amount, recommend installment payment or letter of credit to reduce risk."
        )
    dimensions["transaction"] = {
        "score": size_score,
        "max": 15,
        "label": "交易规模" if lang == "zh" else "Transaction Size",
    }

    # Calculate total
    total = sum(d["score"] for d in dimensions.values())
    total = max(0, min(100, total))

    # Determine trust level
    if total >= 80:
        level = "高"
        recommendations.append(
            "客户信任度高，可考虑长期合作，适当放宽付款条件。" if lang == "zh"
            else "High trust customer, consider long-term partnership and relaxed payment terms."
        )
    elif total >= 50:
        level = "中"
        recommendations.append(
            "客户信任度中等，按常规流程交易，保持关注。" if lang == "zh"
            else "Medium trust customer, follow standard process, stay attentive."
        )
    else:
        level = "低"
        recommendations.append(
            "客户信任度较低，建议谨慎交易，要求预付或第三方担保。" if lang == "zh"
            else "Low trust customer, recommend cautious trading, require upfront payment or third-party guarantee."
        )

    return TrustScoreResult(
        total=total,
        level=level,
        dimensions=dimensions,
        recommendations=recommendations,
        lang=lang,
    )


def get_trust_level_color(level: str) -> str:
    """Get color for trust level."""
    return {"高": "#009c48", "中": "#f5a623", "低": "#d9364c"}.get(level, "#6c7378")
