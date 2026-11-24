"""Critic Agent: security gate + ML quality gate."""

from __future__ import annotations

from .schemas import (
    AnalysisPlan,
    CriticResult,
    DatasetProfile,
    ModelResult,
    SecurityResult,
)
from .security import SecurityGuardian


class CriticAgent:
    """Reviews both execution safety and model quality.

    Security has priority: an unsafe plan is rejected even if its expected
    model quality would otherwise be excellent.
    """

    def __init__(self, security_guardian: SecurityGuardian | None = None):
        self.security_guardian = security_guardian or SecurityGuardian()

    def review(
        self,
        plan: AnalysisPlan,
        profile: DatasetProfile,
        model_results: tuple[ModelResult, ...],
        inquiry: str = "",
    ) -> CriticResult:
        security = self.security_guardian.inspect(
            plan=plan,
            profile=profile,
            inquiry=inquiry,
        )

        security_result = SecurityResult(
            allowed=security.allowed,
            risk_level=security.risk_level,
            risk_types=security.risk_types,
            violations=security.violations,
            warnings=security.warnings,
            rationale=security.rationale,
        )

        if not security.allowed:
            return CriticResult(
                satisfactory=False,
                score=0.0,
                issues=security.violations,
                recommendations=(
                    "Do not execute the current plan.",
                    "Return to the planner and generate a policy-compliant plan.",
                ),
                next_plan_overrides={},
                security=security_result,
            )

        issues: list[str] = []
        recommendations: list[str] = []
        overrides: dict[str, object] = {}

        if not model_results:
            return CriticResult(
                satisfactory=False,
                score=0.0,
                issues=("No model results were supplied.",),
                recommendations=("Run the planned models before review.",),
                security=security_result,
            )

        best = max(
            model_results,
            key=lambda result: self._score(result, plan.primary_metric),
        )
        best_score = self._score(best, plan.primary_metric)
        score = max(0.0, min(1.0, best_score))

        if (
            profile.class_imbalance_ratio is not None
            and profile.class_imbalance_ratio < 0.75
        ):
            issues.append("Class imbalance is present.")
            if "recall" not in best.metrics:
                recommendations.append(
                    "Report minority-class recall in addition to the primary metric."
                )
            recommendations.append(
                "Use class weighting or balanced sampling during the next training run."
            )
            overrides["class_weight"] = "balanced"
            overrides["validation_strategy"] = "stratified_k_fold"
            score -= 0.12

        if self._is_overfit(best):
            issues.append(
                "Possible overfitting: training performance materially exceeds validation performance."
            )
            recommendations.append(
                "Reduce model complexity and validate with cross-validation."
            )
            overrides["prefer_regularized_models"] = True
            score -= 0.18

        if best_score < self._acceptable_threshold(plan.primary_metric):
            issues.append(
                f"Best {plan.primary_metric or 'available'} score is below the initial acceptance threshold."
            )
            recommendations.append(
                "Review features, data quality, and alternative models before accepting this result."
            )
            score -= 0.20

        for warning in best.warnings:
            issues.append(f"Model warning: {warning}")
            score -= 0.05

        score = round(max(0.0, min(1.0, score)), 3)
        satisfactory = not issues and score >= self._acceptable_threshold(plan.primary_metric)

        if satisfactory:
            recommendations.append(
                "Result passes the initial quality gate; proceed to explainability."
            )

        return CriticResult(
            satisfactory=satisfactory,
            score=score,
            issues=tuple(issues),
            recommendations=tuple(dict.fromkeys(recommendations)),
            next_plan_overrides=overrides,
            security=security_result,
        )

    @staticmethod
    def _score(result: ModelResult, primary_metric: str | None) -> float:
        if primary_metric and primary_metric in result.metrics:
            value = result.metrics[primary_metric]
        elif result.validation_score is not None:
            value = result.validation_score
        elif result.metrics:
            value = next(iter(result.metrics.values()))
        else:
            return 0.0

        return 1 / (1 + value) if primary_metric in {"rmse", "mae", "mse"} else value

    @staticmethod
    def _is_overfit(result: ModelResult) -> bool:
        return (
            result.train_score is not None
            and result.validation_score is not None
            and result.train_score - result.validation_score >= 0.15
        )

    @staticmethod
    def _acceptable_threshold(primary_metric: str | None) -> float:
        return 0.50 if primary_metric in {"rmse", "mae", "mse"} else 0.65
