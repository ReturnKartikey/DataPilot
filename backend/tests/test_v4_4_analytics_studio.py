import pandas as pd
from data_pilot.analytics.studio import run_analytics_studio

def test_fallback_plan_executes_top_five_grouped_results(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    df=pd.DataFrame({"region":["A","B","C","D","E","F"],"revenue":[10,60,50,40,30,20]})
    out=run_analytics_studio(df,"show top 5 regions by average revenue")
    assert len(out["result"]["grouped_results"]) == 5
    assert out["result"]["grouped_results"][0]["region"] == "B"
    assert out["execution"]["planner_provider"] == "deterministic_fallback"

def test_diagnostic_produces_ranked_correlations(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    df=pd.DataFrame({"price":[10,20,30,40,50],"size":[1,2,3,4,5],"age":[5,4,3,2,1],"noise":[2,5,1,4,3]})
    out=run_analytics_studio(df,"what factors correlate with price")
    assert out["result"]["top_factors"]
    assert out["result"]["top_factors"][0]["feature"] == "size"

def test_category_counts_for_sentiment(monkeypatch):
    for k in ("OPENROUTER_API_KEY","OPENAI_API_KEY","LLM_API_KEY","GEMINI_API_KEY"):
        monkeypatch.delenv(k,raising=False)
    df=pd.DataFrame({"airline_sentiment":["neutral","positive","neutral","negative","neutral"]})
    out=run_analytics_studio(df,"count airline_sentiment")
    assert out["result"]["value_counts"][0] == {"value":"neutral","count":3}

def test_numeric_filter_applied(monkeypatch):
    for k in ("OPENROUTER_API_KEY","OPENAI_API_KEY","LLM_API_KEY","GEMINI_API_KEY"):
        monkeypatch.delenv(k,raising=False)
    df=pd.DataFrame({"score":[1,2,3,4],"team":["A","A","B","B"]})
    # deterministic fallback is conservative; validate execution directly through a generated plan
    from data_pilot.analytics.studio import _execute, _validate_plan
    plan=_validate_plan({"analytics_type":"descriptive","column":"score","filters":[{"column":"score","operator":"gte","value":3}],"chart":{"type":"histogram"}},df,"scores >= 3")
    result=_execute(df,plan)
    assert result["rows_analyzed"] == 2
