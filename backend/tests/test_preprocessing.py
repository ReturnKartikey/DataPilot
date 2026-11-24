import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from data_pilot.agents.preprocessing import PreprocessingAgent
from data_pilot.pipeline import run_pipeline
from data_pilot.profiler import profile_dataframe


class PreprocessingTests(unittest.TestCase):
    def make_data(self):
        rng = np.random.default_rng(7)
        n = 40
        df = pd.DataFrame({
            "age": rng.integers(18, 70, n).astype(float),
            "income": rng.normal(50000, 10000, n),
            "city": rng.choice(["Delhi", "Noida", "Pune"], n),
            "joined": pd.date_range("2025-01-01", periods=n),
        })
        df.loc[[2, 5], "income"] = np.nan
        df.loc[[3], "city"] = None
        df["churn"] = np.where(df["age"] > 50, "yes", "no")
        return df

    def test_transformer_fits_and_transforms_mixed_data(self):
        df = self.make_data()
        profile = profile_dataframe(df, target_column="churn")
        agent = PreprocessingAgent()
        train = df.iloc[:30].drop(columns=["churn"])
        val = df.iloc[30:].drop(columns=["churn"])
        X_train, X_val, names, transformer = agent.prepare_features(
            train, val, profile, target_column="churn"
        )
        self.assertEqual(len(X_train), 30)
        self.assertEqual(len(X_val), 10)
        self.assertEqual(X_train.shape[1], X_val.shape[1])
        self.assertGreater(len(names), 0)
        self.assertEqual(type(transformer).__name__, "ColumnTransformer")

    def test_pipeline_reports_actual_preprocessing_and_explainability(self):
        result = run_pipeline(
            self.make_data(),
            target_column="churn",
            problem_type="classification",
            inquiry="Predict churn",
        )
        self.assertTrue(result["preprocessing"]["execution"]["fitted"])
        self.assertEqual(result["preprocessing"]["execution"]["fit_scope"], "training split only")
        self.assertGreater(result["preprocessing"]["execution"]["transformed_feature_count"], 0)
        self.assertTrue(result["explainability"].get("best_model"))
        self.assertTrue(result["explainability"].get("feature_importance"))

    def test_pipeline_runs_cross_validation_and_statistics(self):
        df = pd.read_csv(Path(__file__).resolve().parents[1] / "sample_data" / "customer_churn.csv")
        result = run_pipeline(df, inquiry="Predict customer churn", target_column="churn", problem_type="classification")
        self.assertIn("statistics", result)
        self.assertGreater(len(result["statistics"]["descriptive"]), 0)
        self.assertIn("cross_validation", result)
        self.assertTrue(result["cross_validation"]["performed"], result["cross_validation"])
        self.assertIn(result["explainability"].get("method"), {"shap", "native_feature_importance", "native_coefficient_magnitude"})


if __name__ == "__main__":
    unittest.main()
