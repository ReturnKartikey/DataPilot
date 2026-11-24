import unittest

from data_pilot.agents import (
    ColumnProfile,
    CriticAgent,
    DatasetProfile,
    ModelResult,
    Objective,
    PlannerAgent,
)


class PlannerAgentTests(unittest.TestCase):
    def test_creates_imbalanced_classification_plan(self):
        profile = DatasetProfile(
            rows=500,
            columns=(
                ColumnProfile("age", "numeric", 60, missing_count=4),
                ColumnProfile("churn", "categorical", 2),
            ),
            duplicate_rows=3,
            potential_target_columns=("churn",),
            class_imbalance_ratio=0.20,
        )
        plan = PlannerAgent().create_plan(profile, Objective(text="Predict customer churn"))
        self.assertEqual(plan.problem_type, "classification")
        self.assertEqual(plan.target_column, "churn")
        self.assertEqual(plan.primary_metric, "f1_weighted")
        self.assertEqual(plan.validation_strategy, "stratified_k_fold")

    def test_requires_explicit_choice_for_multiple_targets(self):
        profile = DatasetProfile(
            rows=10,
            columns=(ColumnProfile("a", "numeric", 5), ColumnProfile("b", "numeric", 5)),
            potential_target_columns=("a", "b"),
        )
        plan = PlannerAgent().create_plan(profile)
        self.assertEqual(plan.problem_type, "unknown")
        self.assertIn("Multiple potential target", plan.warnings[0])


class CriticAgentTests(unittest.TestCase):
    def test_flags_imbalance_and_overfitting(self):
        profile = DatasetProfile(
            rows=500,
            columns=(ColumnProfile("churn", "categorical", 2),),
            class_imbalance_ratio=0.25,
        )
        plan = PlannerAgent().create_plan(profile, Objective(target_column="churn"))
        result = ModelResult(
            "random_forest_classifier",
            {"f1_weighted": 0.60},
            train_score=0.98,
            validation_score=0.60,
        )
        critic = CriticAgent().review(plan, profile, (result,))
        self.assertFalse(critic.satisfactory)
        self.assertTrue(any("imbalance" in issue.lower() for issue in critic.issues))
        self.assertTrue(any("overfitting" in issue.lower() for issue in critic.issues))
        self.assertEqual(critic.next_plan_overrides["class_weight"], "balanced")

    def test_accepts_strong_regression_result(self):
        profile = DatasetProfile(
            rows=500,
            columns=(ColumnProfile("price", "numeric", 400),),
            potential_target_columns=("price",),
        )
        plan = PlannerAgent().create_plan(profile)
        result = ModelResult("ridge_regression", {"rmse": 0.2}, train_score=0.85, validation_score=0.8)
        critic = CriticAgent().review(plan, profile, (result,))
        self.assertTrue(critic.satisfactory)
        self.assertEqual(critic.issues, ())


if __name__ == "__main__":
    unittest.main()
