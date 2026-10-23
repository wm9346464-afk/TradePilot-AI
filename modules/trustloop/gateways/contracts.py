"""Adapter from the existing contract checker into TrustLoop models."""

from __future__ import annotations

import hashlib

from modules.contract_checker import check_contract

from ..enums import RiskDecision, RiskSeverity, RiskType
from ..models import RiskAssessment, RiskItem


TYPE_MAP = {
    "文字错误": RiskType.TYPO,
    "条款完整性": RiskType.COMPLETENESS,
    "数据一致性": RiskType.CONSISTENCY,
    "数据错误": RiskType.DATA_ERROR,
    "风险提示": RiskType.RISK,
    "合规性": RiskType.COMPLIANCE,
    "格式问题": RiskType.FORMAT,
}

SEVERITY_MAP = {
    "高": RiskSeverity.HIGH,
    "High": RiskSeverity.HIGH,
    "high": RiskSeverity.HIGH,
    "中": RiskSeverity.MEDIUM,
    "Medium": RiskSeverity.MEDIUM,
    "medium": RiskSeverity.MEDIUM,
    "低": RiskSeverity.LOW,
    "Low": RiskSeverity.LOW,
    "low": RiskSeverity.LOW,
}


class ExistingContractReviewGateway:
    def review(
        self,
        contract_text: str,
        *,
        use_ai: bool = False,
        force_demo: bool = False,
        lang: str = "zh",
    ) -> RiskAssessment:
        result = check_contract(
            contract_text,
            use_ai=use_ai,
            force_demo=force_demo,
            lang=lang,
        )
        issues: list[RiskItem] = []
        for raw in result.get("issues", []):
            original = str(raw.get("original", "") or "")
            evidence = original if original and original in contract_text else None
            issues.append(
                RiskItem(
                    type=TYPE_MAP.get(raw.get("type"), RiskType.RISK),
                    severity=SEVERITY_MAP.get(raw.get("severity"), RiskSeverity.LOW),
                    original=original,
                    suggestion=str(raw.get("suggestion", "") or ""),
                    description=str(raw.get("description", "") or ""),
                    evidence_quote=evidence,
                )
            )

        high_count = sum(item.severity == RiskSeverity.HIGH for item in issues)
        medium_count = sum(item.severity == RiskSeverity.MEDIUM for item in issues)
        low_count = sum(item.severity == RiskSeverity.LOW for item in issues)
        if high_count >= 3:
            decision = RiskDecision.BLOCK
        elif high_count or medium_count:
            decision = RiskDecision.REVIEW
        else:
            decision = RiskDecision.PROCEED

        return RiskAssessment(
            issues=issues,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            decision=decision,
            contract_hash=hashlib.sha256(contract_text.encode("utf-8")).hexdigest(),
            mode_code=str(result.get("mode_code", "RULE_ONLY")),
        )

