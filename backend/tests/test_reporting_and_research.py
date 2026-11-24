"""Tests for ReportingAgent and ResearchAgent."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from data_pilot.agents.reporting import ReportingAgent
from data_pilot.agents.research import ResearchAgent
from data_pilot.agents.schemas import DatasetProfile, ColumnProfile, AnalysisPlan, ModelResult


class ReportingAgentTests(unittest.TestCase):
    def setUp(self):
        self.reporting = ReportingAgent()

    def test_facts_extraction(self):
        sample_result = {
            "status": "success",
            "dataset_summary": {"rows": 100, "columns_count": 5, "columns": []},
            "plan": {"goal": "Predict test target", "problem_type": "classification", "target_column": "target"},
            "models": [{"model_name": "random_forest_classifier", "validation_score": 0.85, "metrics": {"accuracy": 0.85}}],
            "critic": {"score": 0.9, "satisfactory": True, "issues": [], "recommendations": []},
        }
        facts = self.reporting._facts(sample_result, dataset_name="unit_test_data")
        self.assertEqual(facts["dataset_name"], "unit_test_data")
        self.assertEqual(facts["rows"], 100)
        self.assertEqual(facts["problem_type"], "classification")
        self.assertEqual(facts["target"], "target")
        self.assertEqual(len(facts["models"]), 1)

    def test_generate_markdown_report_structure(self):
        sample_result = {
            "status": "success",
            "dataset_summary": {"rows": 50, "columns_count": 3, "warnings": ["Missing values present"]},
            "plan": {"goal": "Estimate price", "problem_type": "regression", "target_column": "price"},
            "models": [{"model_name": "linear_regression", "validation_score": 0.82, "metrics": {"rmse": 0.15, "r2": 0.82}}],
            "critic": {"score": 0.88, "satisfactory": True, "issues": ["Minor outlier risk"], "recommendations": ["Inspect residual plots"]},
            "security": {"allowed": True, "risk_level": "low", "rationale": "Verified"},
            "research": {"findings": [{"topic": "Small-sample validation", "recommendation": "Use k-fold"}]},
        }
        report = self.reporting.generate(sample_result, dataset_name="housing_data")
        self.assertEqual(report["format"], "markdown")
        md = report["markdown"]
        self.assertIn("# Data Pilot Analysis Report — housing_data", md)
        self.assertIn("## Executive summary", md)
        self.assertIn("## Dataset overview", md)
        self.assertIn("## Security review", md)
        self.assertIn("## Model evaluation", md)
        self.assertIn("## Critic findings", md)
        self.assertIn("## Research and methodology", md)
        self.assertIn("## Limitations", md)

    def test_question_specific_poisonous_percentage_and_report_chart(self):
        sample_result = {
            "status": "success",
            "dataset_summary": {"rows": 8124, "columns_count": 2, "duplicate_rows": 0, "warnings": []},
            "plan": {"goal": "what percentage of mushrooms are poisonous", "problem_type": "classification", "target_column": "class"},
            "models": [], "critic": {}, "security": {}, "preprocessing": {}, "explainability": {}, "research": {},
            "eda": {
                "target_distribution": {"e": 4208, "p": 3916},
                "target_distribution_percentages": {"e": 51.8, "p": 48.2},
                "target_distribution_rows": [
                    {"label": "e", "count": 4208, "percentage": 51.8},
                    {"label": "p", "count": 3916, "percentage": 48.2},
                ],
                "categorical_summary": {"odor": {"almond": 4208, "foul": 3916}},
            },
        }
        report = self.reporting.generate(sample_result, dataset_name="mushrooms.csv")
        self.assertEqual(report["question_answer"]["count"], 3916)
        self.assertEqual(report["question_answer"]["total"], 8124)
        self.assertEqual(report["question_answer"]["percentage"], 48.2)
        self.assertIn("48.20%", report["markdown"])
        self.assertGreaterEqual(len(report["charts"]), 1)

    def test_generate_when_no_models_trained(self):
        sample_result = {
            "status": "partial",
            "dataset_summary": {"rows": 20, "columns_count": 2},
            "plan": {"goal": "Exploration", "problem_type": "unknown", "target_column": None},
            "models": [],
            "critic": {"score": 0.0, "satisfactory": False, "issues": []},
        }
        report = self.reporting.generate(sample_result, dataset_name="unlabeled")
        self.assertIn("No predictive model was trained", report["markdown"])


class ResearchAgentTests(unittest.TestCase):
    def setUp(self):
        self.research = ResearchAgent()

    def test_offline_findings_triggers(self):
        import os
        from unittest.mock import patch
        offline = patch.dict(os.environ, {"DATAPILOT_ENABLE_LIVE_RESEARCH": "false"})
        offline.start()
        self.addCleanup(offline.stop)
        profile = DatasetProfile(
            rows=200,  # small sample < 500
            columns=(
                ColumnProfile(name="feat1", kind="numeric", unique_count=100, missing_count=5),  # missing data
                ColumnProfile(name="target", kind="categorical", unique_count=2, missing_count=0),
            ),
            duplicate_rows=0,
            warnings=(),
            potential_target_columns=("target",),
            class_imbalance_ratio=0.3,  # severe imbalance < 0.75
        )
        plan = AnalysisPlan(
            goal="Predict churn",
            target_column="target",
            problem_type="classification",
            steps=("profile", "clean", "eda", "train_models"),
            recommended_models=("logistic_regression",),
            primary_metric="f1_weighted",
            validation_strategy="stratified_k_fold",
            assumptions=(),
            warnings=(),
        )
        preprocessing = {"execution": {"fitted": True}}

        investigation = self.research.investigate(profile, plan, models=(), preprocessing=preprocessing)
        self.assertEqual(investigation["mode"], "offline_methodology_guidance")
        self.assertFalse(investigation["external_sources_used"])
        topics = [f["topic"] for f in investigation["findings"]]
        self.assertIn("Small-sample validation", topics)
        self.assertIn("Class imbalance", topics)
        self.assertIn("Missing data", topics)
        self.assertIn("Classification evaluation", topics)
        self.assertIn("Preprocessing validation", topics)


if __name__ == "__main__":
    unittest.main()

