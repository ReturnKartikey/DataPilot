"""Pre-execution security guardian for Data Pilot.

This is a project-specific guardrail inspired by the pre-execution safety
principle used in research such as Safiron/AuraGen. It is deliberately
rule-based and deterministic: the LLM/planner may propose a plan, but it
cannot bypass this policy before tools or ML jobs execute.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .schemas import AnalysisPlan, DatasetProfile


@dataclass(frozen=True)
class SecurityDecision:
    allowed: bool
    risk_level: str
    risk_types: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "risk_level": self.risk_level,
            "risk_types": list(self.risk_types),
            "violations": list(self.violations),
            "warnings": list(self.warnings),
            "rationale": self.rationale,
        }


class SecurityGuardian:
    """Validates plans before they can reach execution tools."""

    ALLOWED_STEPS = {
        "profile",
        "clean",
        "eda",
        "feature_engineering",
        "train_models",
        "evaluate",
        "explain",
        "autonomous_replanning",
    }

    ALLOWED_MODELS = {
        "logistic_regression",
        "decision_tree_classifier",
        "random_forest_classifier",
        "gradient_boosting_classifier",
        "linear_regression",
        "ridge_regression",
        "decision_tree_regressor",
        "random_forest_regressor",
        "gradient_boosting_regressor",
        "xgboost_classifier",
        "xgboost_regressor",
    }

    FORBIDDEN_TERMS = (
        "execute_shell",
        "shell",
        "subprocess",
        "os.system",
        "eval(",
        "exec(",
        "powershell",
        "cmd.exe",
        "curl ",
        "wget ",
        "rm -rf",
        "delete_database",
        "drop_database",
        "upload_dataset",
        "send_dataset",
        "external_url",
        "exfiltrate",
    )

    PROMPT_INJECTION_PATTERNS = (
        r"ignore previous instructions",
        r"ignore all previous instructions",
        r"ignore the previous instructions",
        r"reveal system prompt",
        r"show system prompt",
        r"developer message",
        r"bypass security",
        r"disable guardrail",
        r"disable safety",
        r"override policy",
    )

    def inspect(
        self,
        plan: AnalysisPlan,
        profile: DatasetProfile,
        inquiry: str = "",
    ) -> SecurityDecision:
        violations: list[str] = []
        warnings: list[str] = []
        risk_types: set[str] = set()

        for step in plan.steps:
            if step not in self.ALLOWED_STEPS:
                violations.append(f"Unauthorized analysis step: {step}")
                risk_types.add("unauthorized_action")

        for model in plan.recommended_models:
            if model not in self.ALLOWED_MODELS:
                violations.append(f"Unauthorized model requested: {model}")
                risk_types.add("unauthorized_model")

        if plan.target_column and profile.column(plan.target_column) is None:
            violations.append(
                f"Target column '{plan.target_column}' does not exist in the dataset."
            )
            risk_types.add("invalid_data_access")

        text = " ".join(
            part for part in (
                inquiry or "",
                plan.goal or "",
                " ".join(plan.steps),
                " ".join(plan.assumptions),
            )
            if part
        ).lower()

        for term in self.FORBIDDEN_TERMS:
            term_lower = term.lower()
            if re.fullmatch(r"[a-z0-9_]+", term_lower):
                matched = bool(re.search(r"(?<![a-z0-9_])" + re.escape(term_lower) + r"(?![a-z0-9_])", text))
            else:
                matched = term_lower in text
            if matched:
                violations.append(f"Potentially dangerous instruction detected: '{term}'")
                if term in {"upload_dataset", "send_dataset", "external_url", "exfiltrate"}:
                    risk_types.add("data_exfiltration")
                else:
                    risk_types.add("unsafe_instruction")

        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text):
                violations.append(f"Potential prompt injection detected: '{pattern}'")
                risk_types.add("prompt_injection")

        if profile.rows > 1_000_000:
            warnings.append("Dataset exceeds the default execution size limit of 1,000,000 rows.")
            risk_types.add("resource_risk")

        if violations:
            critical_types = {
                "prompt_injection",
                "unsafe_instruction",
                "unauthorized_action",
                "data_exfiltration",
            }
            risk_level = "critical" if risk_types.intersection(critical_types) else "high"
            return SecurityDecision(
                allowed=False,
                risk_level=risk_level,
                risk_types=tuple(sorted(risk_types)),
                violations=tuple(violations),
                warnings=tuple(warnings),
                rationale=(
                    "The proposed analysis plan failed the pre-execution security policy "
                    "and must not be executed."
                ),
            )

        return SecurityDecision(
            allowed=True,
            risk_level="medium" if warnings else "low",
            risk_types=tuple(sorted(risk_types)),
            violations=(),
            warnings=tuple(warnings),
            rationale=(
                "The analysis plan contains only allowlisted operations and passed "
                "pre-execution security checks."
            ),
        )
