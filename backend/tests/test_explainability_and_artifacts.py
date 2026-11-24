"""Tests for ExplainabilityAgent and ArtifactStore."""
from __future__ import annotations

import tempfile
import unittest
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, LinearRegression

from data_pilot.agents.explainability import ExplainabilityAgent
from data_pilot.artifacts import ArtifactStore


class ExplainabilityAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = ExplainabilityAgent()
        np.random.seed(42)
        self.X = np.random.randn(40, 4)
        self.y = (self.X[:, 0] + self.X[:, 1] > 0).astype(int)
        self.feature_names = ["feat_a", "feat_b", "feat_c", "feat_d"]

    def test_explain_tree_classifier(self):
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(self.X, self.y)
        res = self.agent.explain_model(model, self.feature_names, X_sample=self.X)
        self.assertEqual(res["model_type"], "RandomForestClassifier")
        self.assertIn("feat_a", res["feature_importance"])
        self.assertIn("feat_b", res["feature_importance"])
        self.assertIn(res["method"], {"shap", "native_feature_importance"})

    def test_explain_linear_model(self):
        model = LogisticRegression()
        model.fit(self.X, self.y)
        res = self.agent.explain_model(model, self.feature_names, X_sample=self.X)
        self.assertEqual(res["model_type"], "LogisticRegression")
        self.assertIn("feat_a", res["feature_importance"])
        self.assertIn(res["method"], {"shap", "native_coefficient_magnitude"})

    def test_explain_regression_model(self):
        y_reg = self.X[:, 0] * 2.5 + self.X[:, 1] * 1.2
        model = LinearRegression()
        model.fit(self.X, y_reg)
        res = self.agent.explain_model(model, self.feature_names, X_sample=self.X)
        self.assertEqual(res["model_type"], "LinearRegression")
        self.assertIn("feat_a", res["feature_importance"])


class ArtifactStoreTests(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir)
            model = LogisticRegression()
            model.fit([[1.0], [2.0], [3.0]], [0, 0, 1])

            save_res = store.save_model(
                estimator=model,
                preprocessor=None,
                model_name="logistic_regression",
                feature_names=["f1"],
                datetime_columns=[],
                target_classes=["No", "Yes"],
            )

            self.assertIn("artifact_id", save_res)
            artifact_id = save_res["artifact_id"]

            loaded = store.load_model(artifact_id)
            self.assertEqual(loaded["model_name"], "logistic_regression")
            self.assertEqual(loaded["feature_names"], ["f1"])
            self.assertEqual(loaded["target_classes"], ["No", "Yes"])

    def test_invalid_artifact_id_raises_value_or_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(tmpdir)
            with self.assertRaises(ValueError):
                store.load_model("not-a-valid-uuid")

            with self.assertRaises(FileNotFoundError):
                store.load_model("12345678-1234-5678-1234-567812345678")


if __name__ == "__main__":
    unittest.main()

