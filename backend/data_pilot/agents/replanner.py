"""Bounded, policy-constrained replanning after Critic feedback."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from dataclasses import replace
from typing import Any
from .schemas import AnalysisPlan, CriticResult

@dataclass(frozen=True)
class ReplanDecision:
    attempted: bool
    reason: str
    selected_models: tuple[str, ...] = ()
    applied_overrides: dict[str, Any] | None = None
    def to_dict(self): return asdict(self)

class ReplannerAgent:
    """Creates one bounded alternative plan; it never emits executable code."""
    def create_revision(self, plan: AnalysisPlan, critic: CriticResult, attempted_models: set[str], max_models: int = 2):
        if critic.satisfactory:
            return plan, ReplanDecision(False, "Critic accepted the current result.")
        if plan.problem_type == "unknown":
            return plan, ReplanDecision(False, "No predictive target is available to replan.")
        candidates = [name for name in plan.recommended_models if name not in attempted_models]
        overrides = dict(critic.next_plan_overrides or {})
        if overrides.get("prefer_regularized_models"):
            preferred = [n for n in candidates if n in {"ridge_regression", "logistic_regression", "decision_tree_classifier", "decision_tree_regressor"}]
            candidates = preferred + [n for n in candidates if n not in preferred]
        selected = tuple(candidates[:max_models])
        if not selected:
            return plan, ReplanDecision(False, "No untried allowlisted models remain.", applied_overrides=overrides)
        revised = replace(
            plan,
            recommended_models=selected,
            steps=plan.steps + ("autonomous_replanning",),
            assumptions=plan.assumptions + ("Autonomous loop executed: Replanned once using Critic feedback; only untried allowlisted models were selected.",),
        )
        return revised, ReplanDecision(True, "Critic rejected the first run; trying alternative allowlisted models.", selected, overrides)
