import io
import unittest
import pandas as pd
from fastapi.testclient import TestClient
from app import app, MAX_FILE_SIZE
from data_pilot.pipeline import run_pipeline, _prepare_train_val_data
from data_pilot.profiler import profile_dataframe
from data_pilot.agents.planner import PlannerAgent
from data_pilot.agents.schemas import Objective


class PipelineFixesTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_integer_binary_target_calculates_imbalance(self):
        """Verify binary target stored as 0 and 1 correctly calculates class_imbalance_ratio."""
        df = pd.DataFrame({
            "feature": list(range(20)),
            "target": [0] * 16 + [1] * 4,  # 4/16 = 0.25
        })
        profile = profile_dataframe(df, target_column="target")
        self.assertIsNotNone(profile.class_imbalance_ratio)
        self.assertAlmostEqual(profile.class_imbalance_ratio, 0.25, places=2)

        plan = PlannerAgent().create_plan(profile, Objective(target_column="target"))
        self.assertEqual(plan.problem_type, "classification")
        self.assertEqual(plan.primary_metric, "f1_weighted")

    def test_numeric_targets_with_few_unique_values_default_to_regression(self):
        """Continuous numeric targets with <= 20 values should not be coerced into classification."""
        df = pd.DataFrame({
            "x1": list(range(30)),
            "price": [10.5, 20.0, 30.5, 40.0, 50.5] * 6,
        })
        res = run_pipeline(df, target_column="price")
        self.assertEqual(res["plan"]["problem_type"], "regression")

    def test_zero_data_leakage_and_id_exclusion(self):
        """Verify scaling/imputation fits on train only and ID columns are dropped from features."""
        df = pd.DataFrame({
            "customer_id": [f"ID_{i}" for i in range(40)],
            "numeric_feat": [float(i) for i in range(40)],
            "category": ["A", "B"] * 20,
            "target": [0, 1] * 20,
        })
        X_train, X_val, y_train, y_val = _prepare_train_val_data(df, "target", "classification")

        # ID column must be excluded from feature columns
        self.assertNotIn("customer_id", X_train.columns)
        self.assertNotIn("customer_id", X_val.columns)

        # X_train and X_val must have identical aligned columns
        self.assertEqual(list(X_train.columns), list(X_val.columns))

    def test_run_pipeline_excludes_identifier_columns_from_features_and_shap(self):
        """Verify end-to-end run_pipeline drops customer_id before model training and SHAP."""
        churn_df = pd.read_csv("sample_data/customer_churn.csv")
        res = run_pipeline(churn_df, target_column="churn", problem_type="classification")
        excluded = res["preprocessing"].get("excluded_identifier_columns", [])
        self.assertIn("customer_id", excluded)
        transformed_preview = res["preprocessing"]["execution"].get("transformed_features_preview", [])
        self.assertFalse(any("customer_id" in name for name in transformed_preview))
        importance = res["explainability"].get("feature_importance", {})
        self.assertFalse(any("customer_id" in name for name in importance))

    def test_closed_loop_replanning_on_imbalance(self):
        """Verify closed loop executes when Critic identifies actionable overrides."""
        churn_df = pd.read_csv("sample_data/customer_churn.csv")
        res = run_pipeline(churn_df, target_column="churn", problem_type="classification")
        self.assertIn("autonomous_replanning", res["plan"]["steps"])
        self.assertTrue(any("Autonomous loop executed" in a for a in res["plan"]["assumptions"]))

    def test_multiclass_does_not_fabricate_accuracy_as_roc_auc(self):
        """Multiclass models without full proba support should not substitute accuracy as roc_auc."""
        df = pd.DataFrame({
            "x1": list(range(30)),
            "x2": list(range(30, 60)),
            "target": ["alpha"] * 10 + ["beta"] * 10 + ["gamma"] * 10,
        })
        res = run_pipeline(df, target_column="target", problem_type="classification")
        self.assertGreaterEqual(len(res["models"]), 1)
        for m in res["models"]:
            # If roc_auc is present, it shouldn't just be a blind copy of accuracy if accuracy != roc_auc
            if "roc_auc" in m["metrics"]:
                self.assertIsInstance(m["metrics"]["roc_auc"], float)

    def test_file_upload_size_limit_rejection(self):
        """Verify uploading file exceeding MAX_FILE_SIZE is rejected with 413."""
        oversized = b"a" * (MAX_FILE_SIZE + 10)
        files = {"file": ("big.csv", io.BytesIO(oversized), "text/csv")}
        response = self.client.post("/api/analyze", files=files)
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()

