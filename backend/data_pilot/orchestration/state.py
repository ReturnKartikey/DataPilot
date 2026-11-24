from typing import Any, TypedDict
import pandas as pd
class DataPilotState(TypedDict, total=False):
    dataframe: pd.DataFrame
    inquiry: str
    target_column: str | None
    problem_type: str
    dataset_name: str
    result: dict[str, Any]
    status: str
    events: list[dict[str, Any]]
    error: str
