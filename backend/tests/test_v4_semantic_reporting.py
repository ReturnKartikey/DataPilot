import unittest
from unittest.mock import patch
import pandas as pd

from data_pilot.pipeline import _infer_target_from_question, _resolve_context
from data_pilot.profiler import profile_dataframe
from data_pilot.agents.reporting import ReportingAgent
from data_pilot.agents.eda import EDAAgent
from data_pilot.agents.research import ResearchAgent
from data_pilot.agents.schemas import DatasetProfile, ColumnProfile, AnalysisPlan


class SemanticTargetTests(unittest.TestCase):
    def test_neutral_sentiment_selects_sentiment_not_timezone(self):
        df = pd.DataFrame({
            "tweet_id": [1, 2, 3, 4],
            "user_timezone": ["Eastern", "Pacific", "Central", "Eastern"],
            "airline_sentiment": ["neutral", "negative", "positive", "neutral"],
        })
        question = "how many tweets are of neutral sentiment"
        self.assertEqual(_infer_target_from_question(df, question), "airline_sentiment")
        profile = profile_dataframe(df)
        target, problem_type = _resolve_context(df, profile, question, None, "unknown")
        self.assertEqual(target, "airline_sentiment")
        self.assertEqual(problem_type, "classification")


    def test_target_distribution_uses_valid_label_denominator(self):
        df = pd.DataFrame({"sentiment": ["neutral", "negative", None, "neutral"]})
        eda = EDAAgent().analyze(df, target_column="sentiment")
        self.assertEqual(sum(eda["target_distribution"].values()), 3)
        self.assertEqual(eda["target_distribution_percentages"]["neutral"], 66.67)

    def test_pie_chart_request_is_preserved(self):
        result = {
            "plan": {"goal": "show a pie chart of sentiment", "target_column": "airline_sentiment"},
            "eda": {
                "target_distribution": {"neutral": 2, "positive": 1, "negative": 1},
                "target_distribution_percentages": {"neutral": 50, "positive": 25, "negative": 25},
                "target_distribution_rows": [
                    {"label": "neutral", "count": 2, "percentage": 50},
                    {"label": "positive", "count": 1, "percentage": 25},
                    {"label": "negative", "count": 1, "percentage": 25},
                ],
            },
        }
        charts = ReportingAgent._build_charts(result)
        self.assertEqual(charts[0]["type"], "pie")

    def test_neutral_question_answer_uses_actual_eda_counts(self):
        result = {
            "plan": {"goal": "how many tweets are of neutral sentiment", "target_column": "airline_sentiment"},
            "eda": {
                "target_distribution": {"neutral": 2, "positive": 1, "negative": 1},
                "target_distribution_percentages": {"neutral": 50, "positive": 25, "negative": 25},
            },
        }
        answer = ReportingAgent._question_specific_answer(result, "tweets.csv")
        self.assertEqual(answer["count"], 2)
        self.assertEqual(answer["total"], 4)
        self.assertEqual(answer["percentage"], 50.0)


    def test_research_agent_uses_retrieved_paper_records_when_enabled(self):
        import os
        profile = DatasetProfile(
            rows=1200,
            columns=(ColumnProfile(name="airline_sentiment", kind="categorical", unique_count=3, missing_count=0),
                     ColumnProfile(name="tweet_text", kind="categorical", unique_count=900, missing_count=0)),
            duplicate_rows=0, warnings=(), potential_target_columns=("airline_sentiment",),
            class_imbalance_ratio=0.8,
        )
        plan = AnalysisPlan("classify airline sentiment", "airline_sentiment", "classification",
                            ("profile", "eda", "train_models"), ("logistic_regression",),
                            "f1_weighted", "stratified_k_fold")
        paper = {"title": "Sentiment classification in social media", "authors": ["A. Researcher"],
                 "year": 2023, "doi": "https://doi.org/10.1234/example", "url": "https://doi.org/10.1234/example",
                 "source": "Journal", "abstract": "We study sentiment classification.", "summary": "We study sentiment.",
                 "provider": "OpenAlex", "evidence_level": "abstract"}
        from unittest.mock import patch
        with patch.dict(os.environ, {"DATAPILOT_ENABLE_LIVE_RESEARCH": "true"}):
            with patch.object(ResearchAgent, "_openalex", return_value=[paper]), patch.object(ResearchAgent, "_crossref", return_value=[]):
                result = ResearchAgent().investigate(profile, plan, tuple(), {"execution": {"fitted": False}})
        self.assertEqual(result["mode"], "live_research")
        self.assertEqual(result["sources"][0]["provider"], "OpenAlex")
        self.assertIn("sentiment", result["research_query"].lower())

    def test_openalex_abstract_reconstruction(self):
        abstract = ResearchAgent._abstract_from_inverted_index({"data": [1], "science": [0, 2]})
        self.assertEqual(abstract, "science data science")


if __name__ == "__main__":
    unittest.main()
