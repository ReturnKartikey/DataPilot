"""Allowlisted tool catalogue shared by REST adapter and MCP server."""
from __future__ import annotations

from typing import Any


class ToolRegistry:
    def __init__(self):
        self._tools = {
            "dataset.list_samples": {
                "description": "List built-in sample datasets",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            "dataset.profile": {
                "description": "Profile the bundled customer churn dataset",
                "inputSchema": {
                    "type": "object",
                    "properties": {"target_column": {"type": "string", "minLength": 1, "maxLength": 120}},
                    "additionalProperties": False,
                },
            },
            "dataset.eda": {
                "description": "Run EDA on the bundled customer churn dataset",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            "analysis.run_sample": {
                "description": "Run the full Data Pilot analysis pipeline on a named bundled sample dataset",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sample_id": {"type": "string", "enum": ["churn", "housing", "sales"]},
                        "inquiry": {"type": "string", "maxLength": 1000},
                    },
                    "required": ["sample_id"],
                    "additionalProperties": False,
                },
            },
            "analysis.report": {
                "description": "Retrieve the report for a saved experiment",
                "inputSchema": {
                    "type": "object",
                    "properties": {"experiment_id": {"type": "string", "minLength": 1, "maxLength": 120}},
                    "required": ["experiment_id"],
                    "additionalProperties": False,
                },
            },
            "research.search": {
                "description": "Retrieve evidence excerpts from user-indexed research documents",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "minLength": 1, "maxLength": 1000},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
            "security.self_test": {
                "description": "Run the Security Guardian adversarial self-test",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            "system.capabilities": {
                "description": "Return enabled Data Pilot capabilities and optional integrations",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": n, **spec} for n, spec in self._tools.items()]

    def get(self, name: str):
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered or permitted.")
        return self._tools[name]

    def validate_arguments(self, name: str, arguments: Any) -> dict[str, Any]:
        spec = self.get(name)
        schema = spec.get("inputSchema", {})
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object.")

        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if schema.get("additionalProperties") is False:
            unexpected = set(arguments.keys()) - set(properties.keys())
            if unexpected:
                raise ValueError(f"Unexpected argument(s): {', '.join(sorted(unexpected))}")

        for req in required:
            if req not in arguments or arguments[req] is None or (isinstance(arguments[req], str) and not arguments[req].strip()):
                raise ValueError(f"Missing required argument: '{req}'.")

        cleaned: dict[str, Any] = {}
        for key, value in arguments.items():
            prop = properties.get(key, {})
            expected_type = prop.get("type")
            if expected_type == "string":
                if not isinstance(value, str):
                    raise ValueError(f"Argument '{key}' must be a string.")
                if "minLength" in prop and len(value.strip()) < int(prop["minLength"]):
                    raise ValueError(f"Argument '{key}' must be at least {prop['minLength']} character(s).")
                if "maxLength" in prop and len(value) > int(prop["maxLength"]):
                    raise ValueError(f"Argument '{key}' exceeds maximum length ({prop['maxLength']}).")
                if "enum" in prop and value not in prop["enum"]:
                    raise ValueError(f"Argument '{key}' must be one of: {', '.join(prop['enum'])}.")
            elif expected_type == "integer":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(f"Argument '{key}' must be an integer.")
                if "minimum" in prop and value < int(prop["minimum"]):
                    raise ValueError(f"Argument '{key}' must be >= {prop['minimum']}.")
                if "maximum" in prop and value > int(prop["maximum"]):
                    raise ValueError(f"Argument '{key}' must be <= {prop['maximum']}.")
            cleaned[key] = value
        return cleaned
