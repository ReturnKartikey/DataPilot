from pathlib import Path
import numpy as np
import pandas as pd

from data_pilot.data_engine.selector import PandasEngine, get_engine
from data_pilot.research.rag import ResearchRAG
from data_pilot.agents.statistics import StatisticalAnalysisAgent
from data_pilot.deep_learning import TabularMLPClassifier, TabularMLPRegressor


def test_pandas_engine_profile_is_available_without_duckdb():
    frame = pd.DataFrame({"x": [1, 2, 2], "y": [3, 3, 3]})
    profile = PandasEngine().profile(frame)
    assert profile["engine"] == "pandas"
    assert profile["rows"] == 3
    assert profile["duplicate_rows"] == 1
    assert get_engine(frame).name in {"pandas", "duckdb"}


def test_local_research_rag_indexes_and_retrieves_grounded_passages(tmp_path):
    rag = ResearchRAG(tmp_path / "rag.sqlite3")
    text = ("Class imbalance can distort accuracy in classification tasks. "
            "Use stratified validation and inspect minority-class recall, weighted F1, "
            "precision-recall curves and confusion matrices. " * 8)
    indexed = rag.index_text("Evaluation notes", text, "local notes", "10.1234/example")
    assert indexed["chunks_added"] >= 1
    result = rag.answer_context("How should classification under class imbalance be evaluated?")
    assert result["mode"] == "retrieval_only"
    assert result["sources"]
    assert "minority-class recall" in result["sources"][0]["excerpt"]
    assert rag.status()["indexed_documents"] == 1


def test_multiclass_statistics_can_run_anova_and_chi_square():
    frame = pd.DataFrame({
        "measurement": [1, 2, 2, 3, 7, 8, 8, 9, 13, 14, 14, 15],
        "segment": ["A", "B"] * 6,
        "label": ["low"] * 4 + ["mid"] * 4 + ["high"] * 4,
    })
    result = StatisticalAnalysisAgent().analyze(frame, "label")
    names = {item["test"] for item in result["tests"]}
    assert "one_way_anova" in names
    assert "kruskal_wallis" in names
    assert "chi_square_independence" in names


def test_binary_statistics_include_mann_whitney_u():
    frame = pd.DataFrame({"value": [1, 2, 2, 3, 8, 9, 10, 11], "label": ["A"] * 4 + ["B"] * 4})
    result = StatisticalAnalysisAgent().analyze(frame, "label")
    assert "mann_whitney_u" in {item["test"] for item in result["tests"]}


def test_torch_mlp_classifier_and_regressor_smoke():
    import torch  # noqa: F401
    rng = np.random.default_rng(7)
    X = rng.normal(size=(40, 4)).astype("float32")
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    clf = TabularMLPClassifier(epochs=3, patience=2, hidden_size=16, batch_size=16)
    clf.fit(X, y)
    assert len(clf.predict(X)) == 40
    assert clf.predict_proba(X).shape == (40, 2)
    reg = TabularMLPRegressor(epochs=3, patience=2, hidden_size=16, batch_size=16)
    reg.fit(X, X[:, 0] * 2)
    assert reg.predict(X).shape == (40,)


def test_langgraph_compatibility_fallback_is_explicit(monkeypatch):
    from data_pilot import pipeline
    from data_pilot.orchestration import graph
    if graph.LANGGRAPH_AVAILABLE:
        return
    monkeypatch.setattr(pipeline, "_run_pipeline_core", lambda *args, **kwargs: {
        "status": "success", "plan": {}, "models": [], "eda": {}, "statistics": {},
        "preprocessing": {}, "critic": {}, "explainability": {}, "research": {}, "report": {},
    })
    result = graph.run_langgraph_pipeline(pd.DataFrame({"x": [1, 2]}))
    assert result["orchestration"]["framework"] == "python_fallback"
    assert result["agent_trace"]


def test_v3_research_api_and_tool_catalogue():
    from fastapi.testclient import TestClient
    from app import app
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["version"] == "4.5.0"
    text = "Research methodology discusses stratified validation and class imbalance. " * 8
    indexed = client.post("/api/research/index", json={"title": "Test research note", "text": text, "source": "unit test"})
    assert indexed.status_code == 200
    found = client.post("/api/research/query", json={"query": "stratified validation class imbalance"})
    assert found.status_code == 200 and found.json()["sources"]
    tools = client.get("/api/tools").json()["tools"]
    assert {"analysis.run_sample", "research.search", "system.capabilities"}.issubset({t["name"] for t in tools})


def test_saved_agent_trace_endpoint():
    from fastapi.testclient import TestClient
    from app import app, EXPERIMENT_STORE
    experiment_id = EXPERIMENT_STORE.save("trace-test", {
        "status": "success", "orchestration": {"framework": "python_fallback"},
        "agent_trace": [{"agent": "Planner", "status": "completed", "detail": "Plan created"}],
    })
    response = TestClient(app).get(f"/api/history/{experiment_id}/agents")
    assert response.status_code == 200
    assert response.json()["agents"][0]["agent"] == "Planner"
