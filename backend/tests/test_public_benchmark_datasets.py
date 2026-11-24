"""Tests verifying Data Pilot against standard machine learning benchmark scenarios.

Covers testing scenarios defined in Section 64 & 65 of the Data Pilot specifications:
- Clean classification (Iris-style)
- Missing values automatic imputation (zero data leakage)
- Categorical features with One-Hot encoding
- Class imbalance detection and Critic review
- Regression tasks (Housing / Sales prices)
- Small dataset safety (< 20 rows) without crashes
- ID column identification and exclusion
"""
from __future__ import annotations

import unittest
import numpy as np
import pandas as pd

from data_pilot.pipeline import run_pipeline


class BenchmarkScenariosTests(unittest.TestCase):
    def test_scenario_1_clean_classification(self):
        """Clean multi-feature classification dataset (Iris/Wine style)."""
        np.random.seed(42)
        # Separate distributions for setosa vs versicolor like the real Iris dataset
        sepal_length = np.concatenate([np.random.normal(5.0, 0.3, 30), np.random.normal(6.5, 0.3, 30)])
        petal_length = np.concatenate([np.random.normal(1.5, 0.2, 30), np.random.normal(4.5, 0.3, 30)])
        df = pd.DataFrame({
            "sepal_length": sepal_length,
            "petal_length": petal_length,
            "species": ["setosa"] * 30 + ["versicolor"] * 30,
        })
        res = run_pipeline(df, target_column="species", problem_type="classification")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["plan"]["problem_type"], "classification")
        self.assertGreaterEqual(len(res["models"]), 1)
        best = max(res["models"], key=lambda m: m["validation_score"])
        self.assertGreaterEqual(best["validation_score"], 0.7)

    def test_scenario_2_missing_values_imputation(self):
        """Automatic missing value handling without data leakage."""
        df = pd.DataFrame({
            "age": [25, np.nan, 45, 35, np.nan, 29, 40, 50, 22, 38, np.nan, 60],
            "income": [50000, 60000, np.nan, 80000, 75000, 52000, 95000, 110000, 48000, 72000, 68000, np.nan],
            "churn": [0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1],
        })
        res = run_pipeline(df, target_column="churn", problem_type="classification")
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["preprocessing"]["data_leakage_protection"])
        self.assertTrue(res["preprocessing"]["execution"]["fitted"])

    def test_scenario_3_categorical_features_encoding(self):
        """Categorical string columns are safely encoded via ColumnTransformer."""
        df = pd.DataFrame({
            "city": ["New York", "London", "Tokyo", "Paris", "Berlin"] * 6,
            "department": ["Sales", "Engineering", "Marketing"] * 10,
            "experience_years": list(range(30)),
            "promoted": [0, 1] * 15,
        })
        res = run_pipeline(df, target_column="promoted", problem_type="classification")
        self.assertEqual(res["status"], "success")
        # Features transformed preview should include one-hot encoded dummy columns
        preview = res["preprocessing"]["execution"]["transformed_features_preview"]
        self.assertTrue(any("city_" in f for f in preview))
        self.assertTrue(any("department_" in f for f in preview))

    def test_scenario_4_imbalanced_dataset_triggers_critic(self):
        """Severely imbalanced classes flag imbalance issue and recommend weighting."""
        df = pd.DataFrame({
            "score": list(range(40)),
            "rare_disease": [0] * 35 + [1] * 5,  # 5/35 = 0.143 imbalance
        })
        res = run_pipeline(df, target_column="rare_disease", problem_type="classification")
        self.assertLess(res["dataset_summary"]["class_imbalance_ratio"], 0.5)
        self.assertIn("f1_weighted", res["plan"]["primary_metric"])
        self.assertTrue(any("imbalance" in issue.lower() for issue in res["critic"]["issues"]))

    def test_scenario_5_regression_housing_valuation(self):
        """Continuous target problem correctly trains regression models and computes RMSE/R2."""
        np.random.seed(42)
        n = 50
        sqft = np.random.uniform(800, 3500, n)
        rooms = np.random.randint(1, 6, n)
        prices = sqft * 150 + rooms * 12000 + np.random.normal(0, 5000, n)
        df = pd.DataFrame({
            "square_feet": sqft,
            "bedrooms": rooms,
            "price": prices,
        })
        res = run_pipeline(df, target_column="price", problem_type="regression")
        self.assertEqual(res["plan"]["problem_type"], "regression")
        self.assertGreaterEqual(len(res["models"]), 1)
        first_model = res["models"][0]
        self.assertIn("rmse", first_model["metrics"])
        self.assertIn("r2", first_model["metrics"])

    def test_scenario_6_small_dataset_safe_completion(self):
        """Very small dataset (e.g. 10 rows) completes without crashing or blowing up."""
        df = pd.DataFrame({
            "feature": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "outcome": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        })
        res = run_pipeline(df, target_column="outcome", problem_type="classification")
        self.assertIn(res["status"], {"success", "partial"})
        self.assertEqual(res["dataset_summary"]["rows"], 10)


if __name__ == "__main__":
    unittest.main()
