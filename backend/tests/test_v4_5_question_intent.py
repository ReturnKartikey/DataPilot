import pandas as pd
from data_pilot.pipeline import _infer_target_from_question
from data_pilot.agents.reporting import ReportingAgent

def test_obesity_question_maps_to_obesity_category_column():
    df=pd.DataFrame({"Age":[20,30,40],"NObeyesdad":["Normal","Obesity_Type_I","Obesity_Type_II"]})
    assert _infer_target_from_question(df,"which type of obesity has highest patients") == "NObeyesdad"

def test_report_answers_highest_category_from_computed_distribution():
    result={
        "plan":{"goal":"which type of obesity has highest patients","target_column":None},
        "eda":{"target_distribution":{"Normal_Weight":10,"Obesity_Type_I":30,"Obesity_Type_II":20},
               "target_distribution_percentages":{"Normal_Weight":16.67,"Obesity_Type_I":50.0,"Obesity_Type_II":33.33},
               "requested_analysis":{"column":"NObeyesdad"}}
    }
    answer=ReportingAgent._question_specific_answer(result,"obesity_dataset.csv")
    assert answer["category"] == "Obesity_Type_I"
    assert answer["count"] == 30
    assert answer["target_column"] == "NObeyesdad"
    assert answer["answer_type"] == "highest_frequency_category"

def test_question_specific_exact_category_answer_remains_supported():
    result={
        "plan":{"goal":"how many neutral cases are there?","target_column":"sentiment"},
        "eda":{"target_distribution":{"neutral":4,"positive":2},
               "target_distribution_percentages":{"neutral":66.67,"positive":33.33}}
    }
    answer=ReportingAgent._question_specific_answer(result)
    assert answer["category"] == "neutral"
    assert answer["count"] == 4


def test_longest_label_first_prevents_placed_matching_not_placed():
    result={
        "plan":{"goal":"Get me the number of students not placed","target_column":"status"},
        "eda":{"target_distribution":{"Placed":148,"Not Placed":67},
               "target_distribution_percentages":{"Placed":68.84,"Not Placed":31.16}}
    }
    answer=ReportingAgent._question_specific_answer(result)
    assert answer["category"] == "Not Placed"
    assert answer["count"] == 67


def test_smart_auto_routing_and_query_execution_offline(monkeypatch):
    for key in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DATAPILOT_ENABLE_LIVE_RESEARCH", "false")
    monkeypatch.setenv("DATAPILOT_ENABLE_SHAP", "false")
    monkeypatch.setenv("DATAPILOT_ENABLE_MLFLOW", "false")

    from data_pilot.pipeline import run_pipeline

    rows = (
        [{"sl_no": i, "gender": "M", "degree_t": "Sci&Tech", "mba_p": 70.0 + i * 0.2, "salary": 300000.0, "status": "Placed"} for i in range(10)]
        + [{"sl_no": 10 + i, "gender": "F", "degree_t": "Comm&Mgmt", "mba_p": 65.0 + i * 0.2, "salary": 240000.0, "status": "Placed"} for i in range(8)]
        + [{"sl_no": 18 + i, "gender": "M", "degree_t": "Sci&Tech", "mba_p": 54.0 + i * 0.3, "salary": None, "status": "Not Placed"} for i in range(4)]
        + [{"sl_no": 22 + i, "gender": "F", "degree_t": "Others", "mba_p": 56.0 + i * 0.3, "salary": None, "status": "Not Placed"} for i in range(3)]
    )
    df = pd.DataFrame(rows)

    # 1. Negated category count -> question_answering (no ML models trained)
    res_count = run_pipeline(df, inquiry="Get me the number of students not placed", dataset_name="placement.csv")
    assert res_count["models"] == []
    qa = res_count["report"]["question_answer"]
    assert qa["category"] == "Not Placed"
    assert qa["count"] == 7
    assert qa["total"] == 25

    # 2. Multi-column filtered count ("not placed in Sci&Tech")
    res_multi = run_pipeline(df, inquiry="How many students were not placed in Sci&Tech", dataset_name="placement.csv")
    assert res_multi["models"] == []
    assert res_multi["report"]["question_answer"]["count"] == 4

    # 3. Grouped numeric average ("average salary by gender")
    res_avg = run_pipeline(df, inquiry="Compare average salary by gender", dataset_name="placement.csv")
    assert res_avg["models"] == []
    avg_rows = {r["label"]: r["value"] for r in res_avg["report"]["question_answer"]["rows"]}
    assert avg_rows["M"] == 300000.0
    assert avg_rows["F"] == 240000.0

    # 4. Predictive prompt -> routes to ML training
    res_ml = run_pipeline(df, inquiry="Predict student placement status", target_column="status", dataset_name="placement.csv")
    assert len(res_ml["models"]) >= 1
    assert res_ml["plan"]["problem_type"] == "classification"


def test_llm_query_plan_mocked_and_schema_validated(monkeypatch):
    import json
    from unittest.mock import patch
    from data_pilot.llm import intent

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps({
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "analytics_type": "descriptive",
                            "task_mode": "question_answering",
                            "operation": "count",
                            "target": "status",
                            "column": "status",
                            "metric_column": None,
                            "group_by": None,
                            "filters": [
                                {"column": "status", "op": "eq", "value": "not placed"},
                                {"column": "invented_col", "op": "eq", "value": "x"},
                            ],
                            "problem_type": "unknown",
                            "objective": "maximize",
                            "limit": 10,
                        })
                    }
                }]
            }).encode("utf-8")

    df = pd.DataFrame({"status": ["Placed", "Not Placed", "Not Placed"], "salary": [100, None, None]})
    ctx = intent.build_schema_context(df)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with patch.object(intent.urllib.request, "urlopen", return_value=_FakeResp()):
        plan = intent.understand_intent("Get me the number of students not placed", ["status", "salary"], schema_context=ctx)
    assert plan["task_mode"] == "question_answering"
    assert plan["filters"] == [{"column": "status", "op": "eq", "value": "Not Placed"}]
