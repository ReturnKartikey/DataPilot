import pandas as pd

from data_pilot.jobs import AnalysisJobStore
from data_pilot.agents.research import ResearchAgent
from data_pilot.pipeline import run_pipeline


def test_job_store_persists_agent_stage_progress(tmp_path):
    store = AnalysisJobStore(tmp_path / "jobs.sqlite3")
    store.create("job-1", "netflix_titles.csv")
    store.progress("job-1", 42, "Evaluated model: logistic_regression", 5, 11)
    job = store.get("job-1")
    assert job["status"] == "running"
    assert job["progress_percent"] == 42
    assert job["current_stage"] == "Evaluated model: logistic_regression"
    assert job["completed_steps"] == 5
    assert job["total_steps"] == 11


def test_research_query_uses_dataset_domain_not_user_objective():
    from data_pilot.profiler import profile_dataframe
    from data_pilot.agents.schemas import Objective
    from data_pilot.agents.planner import PlannerAgent
    frame = pd.DataFrame({"title": ["A", "B"], "director": ["X", "Y"], "release_year": [2020, 2021]})
    profile = profile_dataframe(frame)
    plan = PlannerAgent().create_plan(profile, Objective(text="top 5 directors"))
    query = ResearchAgent._build_query(profile, plan, "netflix_titles.csv")
    assert "netflix" in query.lower()
    assert "top 5 directors" not in query.lower()
    assert "streaming" in query.lower()


def test_descriptive_entity_ranking_does_not_train_predictive_models(monkeypatch):
    monkeypatch.setenv("DATAPILOT_ENABLE_LIVE_RESEARCH", "false")
    monkeypatch.setenv("DATAPILOT_ENABLE_SHAP", "false")
    monkeypatch.setenv("DATAPILOT_ENABLE_MLFLOW", "false")
    frame = pd.DataFrame({
        "title": [f"movie-{i}" for i in range(16)],
        "directors": ["A, B", "A", "B, C", "A, C", "D", "B", "A", "C"] * 2,
        "release_year": list(range(2000, 2016)),
        "type": ["Movie"] * 16,
    })
    events = []
    result = run_pipeline(frame, "top 5 directors with most number of movies directed",
                          dataset_name="netflix_titles.csv", progress_callback=events.append)
    assert result["plan"]["target_column"] is None
    assert result["plan"]["problem_type"] == "unknown"
    assert result["models"] == []
    assert result["eda"]["requested_analysis"]["column"] == "directors"
    assert result["eda"]["requested_analysis"]["results"][0]["value"] == "A"
    assert events[-1]["progress_percent"] == 91


def test_job_store_marks_previous_process_jobs_interrupted(tmp_path):
    store = AnalysisJobStore(tmp_path / "jobs.sqlite3")
    store.create("stale", "large_dataset.csv")
    store.update("stale", "running", current_stage="Training model")
    assert store.recover_interrupted() == 1
    job = store.get("stale")
    assert job["status"] == "failed"
    assert job["error_code"] == "server_restarted"
    assert job["current_stage"] == "Interrupted by server restart"
