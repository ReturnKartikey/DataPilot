"""Stable, framework-independent contracts for Data Pilot decision agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ColumnKind = Literal["numeric", "categorical", "datetime", "boolean", "unknown"]
ProblemType = Literal["classification", "regression", "unknown"]


@dataclass(frozen=True)
class ColumnProfile:
    """Facts calculated by the deterministic dataset profiler for one column."""

    name: str
    kind: ColumnKind
    unique_count: int
    missing_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DatasetProfile:
    """Profiler output consumed by planning, security and critic agents."""

    rows: int
    columns: tuple[ColumnProfile, ...]
    duplicate_rows: int = 0
    potential_target_columns: tuple[str, ...] = ()
    class_imbalance_ratio: float | None = None
    warnings: tuple[str, ...] = ()

    def column(self, name: str) -> ColumnProfile | None:
        return next((column for column in self.columns if column.name == name), None)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Objective:
    """Optional user intent supplied alongside a dataset."""

    text: str = ""
    target_column: str | None = None
    problem_type: ProblemType = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisPlan:
    """Validated, declarative plan. It contains no executable code."""

    goal: str
    target_column: str | None
    problem_type: ProblemType
    steps: tuple[str, ...]
    recommended_models: tuple[str, ...]
    primary_metric: str | None
    validation_strategy: str
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelResult:
    """Normalized result emitted by the deterministic ML service."""

    model_name: str
    metrics: dict[str, float]
    train_score: float | None = None
    validation_score: float | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SecurityResult:
    """Pre-execution security decision for an agent plan."""

    allowed: bool
    risk_level: str
    risk_types: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CriticResult:
    """Combined security and model-quality review."""

    satisfactory: bool
    score: float
    issues: tuple[str, ...]
    recommendations: tuple[str, ...]
    next_plan_overrides: dict[str, object] = field(default_factory=dict)
    security: SecurityResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
