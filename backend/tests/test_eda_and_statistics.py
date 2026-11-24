"""Tests for EDAAgent and StatisticalAnalysisAgent."""
from __future__ import annotations

import unittest
import numpy as np
import pandas as pd

from data_pilot.agents.eda import EDAAgent
from data_pilot.agents.statistics import StatisticalAnalysisAgent


class EDAAgentTests(unittest.TestCase):
    def setUp(self):
        self.eda = EDAAgent()

    def test_eda_on_mixed_dataset(self):
        df = pd.DataFrame({
            "num1": [10.0, 20.0, 30.0, 40.0, 50.0, 100.0],  # 100 is an outlier
            "num2": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "cat1": ["low", "low", "high", "medium", "high", "high"],
            "target": ["no", "no", "yes", "no", "yes", "yes"],
        })
        res = self.eda.analyze(df, target_column="target")
        self.assertEqual(res["shape"]["rows"], 6)
        self.assertEqual(res["shape"]["columns"], 4)
        self.assertIn("num1", res["numeric_columns"])
        self.assertIn("cat1", res["categorical_columns"])
        self.assertIn("num1", res["histograms"])
        self.assertIn("counts", res["histograms"]["num1"])
        self.assertIn("bin_edges", res["histograms"]["num1"])
        self.assertIn("num1", res["correlations"])
        self.assertIn("cat1", res["categorical_summary"])
        self.assertIn("target_distribution", res)
        self.assertEqual(res["target_distribution"]["yes"], 3)
        self.assertEqual(res["target_distribution"]["no"], 3)

    def test_eda_handles_inf_and_nan(self):
        df = pd.DataFrame({
            "a": [1.0, np.nan, 3.0, np.inf, -np.inf, 6.0],
            "b": ["x", "y", None, "x", "y", "z"],
        })
        res = self.eda.analyze(df)
        self.assertEqual(res["missing_values"]["b"], 1)
        self.assertIn("a", res["numeric_summary"])

    def test_eda_detects_duplicates(self):
        df = pd.DataFrame({
            "x": [1, 2, 1, 2],
            "y": ["a", "b", "a", "b"],
        })
        res = self.eda.analyze(df)
        self.assertTrue(any("duplicate rows detected" in w for w in res["warnings"]))

    def test_eda_without_numeric_columns(self):
        df = pd.DataFrame({
            "text1": ["apple", "banana", "cherry"],
            "text2": ["red", "yellow", "red"],
        })
        res = self.eda.analyze(df)
        self.assertEqual(res["numeric_columns"], [])
        self.assertEqual(res["numeric_summary"], {})
        self.assertEqual(res["histograms"], {})


class StatisticalAnalysisAgentTests(unittest.TestCase):
    def setUp(self):
        self.stats_agent = StatisticalAnalysisAgent()

    def test_descriptive_statistics_and_correlation(self):
        df = pd.DataFrame({
            "val1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
            "val2": [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0],
        })
        res = self.stats_agent.analyze(df)
        self.assertEqual(res["status"], "success")
        self.assertIn("val1", res["descriptive"])
        self.assertIn("variance", res["descriptive"]["val1"])
        self.assertIn("skewness", res["descriptive"]["val1"])
        self.assertIn("kurtosis", res["descriptive"]["val1"])
        self.assertAlmostEqual(res["correlation"]["val1"]["val2"], 1.0, places=4)

    def test_welch_t_test_on_binary_categorical_target(self):
        np.random.seed(42)
        group_a = np.random.normal(loc=10.0, scale=1.0, size=20)
        group_b = np.random.normal(loc=20.0, scale=1.0, size=20)
        df = pd.DataFrame({
            "feature": np.concatenate([group_a, group_b]),
            "label": ["control"] * 20 + ["treatment"] * 20,
        })
        res = self.stats_agent.analyze(df, target_column="label")
        self.assertGreaterEqual(len(res["tests"]), 1)
        test_info = res["tests"][0]
        self.assertEqual(test_info["test"], "welch_t_test")
        self.assertEqual(test_info["feature"], "feature")
        self.assertLess(test_info["p_value"], 0.001)
        self.assertIn("Evidence of a difference", test_info["interpretation"])

    def test_welch_t_test_on_binary_numeric_target(self):
        np.random.seed(42)
        group_0 = np.random.normal(loc=5.0, scale=0.5, size=25)
        group_1 = np.random.normal(loc=15.0, scale=0.5, size=25)
        df = pd.DataFrame({
            "feature": np.concatenate([group_0, group_1]),
            "target": [0] * 25 + [1] * 25,
        })
        res = self.stats_agent.analyze(df, target_column="target")
        self.assertGreaterEqual(len(res["tests"]), 1)
        test_info = res["tests"][0]
        self.assertEqual(test_info["feature"], "feature")
        self.assertLess(test_info["p_value"], 0.001)

    def test_multiclass_target_skips_binary_test_gracefully(self):
        df = pd.DataFrame({
            "f1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "multi_target": ["A", "B", "C", "A", "B", "C"],
        })
        res = self.stats_agent.analyze(df, target_column="multi_target")
        self.assertEqual(res["tests"], [])
        self.assertTrue(any("selected target is not binary" in n for n in res["notes"]))


if __name__ == "__main__":
    unittest.main()

