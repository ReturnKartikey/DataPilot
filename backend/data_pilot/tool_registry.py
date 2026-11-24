"""Allowlisted tool catalogue shared by REST adapter and MCP server."""
from __future__ import annotations
from typing import Any

class ToolRegistry:
    def __init__(self):
        self._tools={
            "dataset.list_samples":{"description":"List built-in sample datasets","inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
            "dataset.profile":{"description":"Profile the bundled customer churn dataset","inputSchema":{"type":"object","properties":{"target_column":{"type":"string"}},"additionalProperties":False}},
            "dataset.eda":{"description":"Run EDA on the bundled customer churn dataset","inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
            "analysis.run_sample":{"description":"Run the full Data Pilot analysis pipeline on a named bundled sample dataset","inputSchema":{"type":"object","properties":{"sample_id":{"type":"string","enum":["churn","housing","sales"]},"inquiry":{"type":"string"}},"required":["sample_id"],"additionalProperties":False}},
            "analysis.report":{"description":"Retrieve the report for a saved experiment","inputSchema":{"type":"object","properties":{"experiment_id":{"type":"string"}},"required":["experiment_id"],"additionalProperties":False}},
            "research.search":{"description":"Retrieve evidence excerpts from user-indexed research documents","inputSchema":{"type":"object","properties":{"query":{"type":"string"},"top_k":{"type":"integer","minimum":1,"maximum":10}},"required":["query"],"additionalProperties":False}},
            "security.self_test":{"description":"Run the Security Guardian adversarial self-test","inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
            "system.capabilities":{"description":"Return enabled Data Pilot capabilities and optional integrations","inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
        }
    def list_tools(self) -> list[dict[str,Any]]: return [{"name":n,**spec} for n,spec in self._tools.items()]
    def get(self,name: str):
        if name not in self._tools: raise KeyError(f"Tool '{name}' is not registered or permitted.")
        return self._tools[name]
