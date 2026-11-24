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
