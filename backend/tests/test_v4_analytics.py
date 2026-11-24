import pandas as pd
from data_pilot.analytics import run_analytics
from data_pilot.llm.intent import understand_intent

def sample():
    return pd.DataFrame({"region":["North","South","North","West"],
                         "revenue":[100,80,120,90],
                         "status":["good","bad","good","bad"]})

def test_descriptive_counts_are_deterministic():
    result=run_analytics(sample(),{"analytics_type":"descriptive","column":"status"})["result"]
    assert result["value_counts"][0]["value"] == "good"
    assert result["value_counts"][0]["count"] == 2

def test_diagnostic_group_comparison():
    result=run_analytics(sample(),{"analytics_type":"diagnostic","target":"revenue","group_by":"region"})["result"]
    assert result["group_comparison"]
    assert "not proof of causation" in result["interpretation_boundary"]

def test_prescriptive_is_explicit_about_limitations():
    result=run_analytics(sample(),{"analytics_type":"prescriptive","decision_variable":"region","value_column":"revenue"})["result"]
    assert result["status"] == "scenario_recommendations"
    assert "not causal optimization" in result["method"]

def test_prescriptive_requires_decision_inputs():
    result=run_analytics(sample(),{"analytics_type":"prescriptive"})["result"]
    assert result["status"] == "needs_inputs"

def test_intent_fallback_never_invents_columns(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY",raising=False)
    monkeypatch.delenv("OPENAI_API_KEY",raising=False)
    monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY",raising=False)
    plan=understand_intent("show region sales",["region","revenue"])
    assert plan["analytics_type"] == "descriptive"
    assert plan["target"] in {"region","revenue",None}
