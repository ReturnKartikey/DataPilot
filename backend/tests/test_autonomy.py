import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from data_pilot.agents.replanner import ReplannerAgent
from data_pilot.agents.reporting import ReportingAgent
from data_pilot.agents.research import ResearchAgent
from data_pilot.profiler import profile_dataframe
from data_pilot.agents.schemas import AnalysisPlan, CriticResult
from data_pilot.history import ExperimentStore
from data_pilot.tool_registry import ToolRegistry
from data_pilot.pipeline import run_pipeline


class AutonomyTests(unittest.TestCase):
    def test_replanner_selects_only_untried_models(self):
        plan = AnalysisPlan("predict", "target", "classification", ("profile", "train_models"), ("logistic_regression", "decision_tree_classifier", "random_forest_classifier"), "accuracy", "holdout")
        critic = CriticResult(False, 0.2, ("weak score",), ("try another model",), {"prefer_regularized_models": True})
        revised, decision = ReplannerAgent().create_revision(plan, critic, {"logistic_regression"})
        self.assertTrue(decision.attempted)
        self.assertNotIn("logistic_regression", revised.recommended_models)
        self.assertTrue(revised.recommended_models)

    def test_reporting_agent_returns_markdown(self):
        report = ReportingAgent().generate({"status":"success", "dataset_summary":{"rows":10,"columns_count":2}, "plan":{"goal":"test"}, "models":[], "critic":{}, "security":{}, "eda":{}, "preprocessing":{}})
        self.assertIn("# Data Pilot Analysis Report", report["markdown"])

    def test_research_agent_generates_dataset_grounded_guidance(self):
        import os
        from unittest.mock import patch
        offline = patch.dict(os.environ, {"DATAPILOT_ENABLE_LIVE_RESEARCH": "false"})
        offline.start()
        self.addCleanup(offline.stop)
        df = pd.DataFrame({"x": [1, 2, None, 4, 5, 6], "target": [0, 0, 1, 1, 0, 1]})
        profile = profile_dataframe(df, target_column="target")
        plan = AnalysisPlan("classify", "target", "classification", ("profile", "train_models"), ("logistic_regression",), "accuracy", "holdout")
        result = ResearchAgent().investigate(profile, plan, tuple(), {"execution": {"fitted": False}})
        self.assertFalse(result["external_sources_used"])
        self.assertGreaterEqual(len(result["findings"]), 1)

    def test_tool_registry_rejects_unregistered_tools(self):
        registry = ToolRegistry()
        self.assertGreaterEqual(len(registry.list_tools()), 3)
        with self.assertRaises(KeyError):
            registry.get("execute.shell")

    def test_experiment_history_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(Path(tmp) / "history.db")
            experiment_id = store.save("sample.csv", {"status":"success", "models":[]})
            self.assertEqual(store.get(experiment_id)["status"], "success")
            self.assertEqual(store.list()[0]["id"], experiment_id)

    def test_pipeline_contains_report_and_replanning_metadata(self):
        rng = np.random.default_rng(13)
        df = pd.DataFrame({"x": rng.normal(size=60), "group": rng.choice(["a", "b"], 60)})
        df["target"] = (df.x > 0).astype(int)
        result = run_pipeline(df, inquiry="classify target", target_column="target", problem_type="classification")
        self.assertIn("replanning", result)
        self.assertIn("# Data Pilot Analysis Report", result["report"]["markdown"])

    def test_llm_report_narrative_uses_structured_provider_and_fallback_facts(self):
        class FakeProvider:
            configured = True
            model = "fake-test-model"
            def generate_json(self, system_prompt, payload):
                self.payload = payload
                return {"executive_interpretation": ["The model shows useful predictive signal."], "key_findings": ["Validation should be repeated."], "recommendations": ["Review class-level errors."], "caveats": ["Do not interpret association as causation."]}
        provider = FakeProvider()
        result = {"status":"success", "dataset_summary":{"rows":20,"columns_count":3}, "plan":{"goal":"Predict outcome","problem_type":"classification","target_column":"outcome"}, "models":[{"model_name":"tree","validation_score":0.8,"metrics":{"accuracy":0.8}}], "critic":{}, "security":{"allowed":True}, "eda":{}, "preprocessing":{}, "explainability":{}, "research":{}}
        report = ReportingAgent(provider=provider).generate(result, "unit.csv")
        self.assertEqual(report["llm"]["status"], "used")
        self.assertIn("The model shows useful predictive signal", report["markdown"])
        self.assertIn("accuracy", report["markdown"])

    def test_llm_report_falls_back_when_provider_fails(self):
        class BrokenProvider:
            configured = True
            model = "fake"
            def generate_json(self, *_): raise TimeoutError()
        report = ReportingAgent(provider=BrokenProvider()).generate({"dataset_summary":{"rows":2,"columns_count":1}})
        self.assertEqual(report["llm"]["status"], "failed_fallback")
        self.assertIn("deterministic report retained", report["markdown"])


if __name__ == "__main__":
    unittest.main()
