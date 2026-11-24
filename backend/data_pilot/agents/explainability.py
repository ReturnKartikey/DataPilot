"""Native and optional SHAP global/local model explanations."""
from __future__ import annotations
import numpy as np


class ExplainabilityAgent:
    def explain_model(self, estimator, feature_names: list[str], X_sample=None) -> dict:
        result = {"model_type": type(estimator).__name__, "method": None, "feature_importance": {}, "local_explanation": {}, "warnings": []}
        shap_enabled = str(__import__("os").getenv("DATAPILOT_ENABLE_SHAP", "true")).lower() in {"1", "true", "yes"}
        if shap_enabled and X_sample is not None and len(X_sample):
            try:
                import shap
                sample = np.asarray(X_sample[:50])
                # TreeExplainer is substantially faster and more stable for tree estimators.
                if hasattr(estimator, "feature_importances_"):
                    explainer = shap.TreeExplainer(estimator)
                    values = explainer.shap_values(sample)
                elif hasattr(estimator, "coef_"):
                    background = sample[: min(30, len(sample))]
                    explainer = shap.LinearExplainer(estimator, background)
                    values = explainer.shap_values(sample)
                else:
                    raise ValueError("No supported fast SHAP explainer for this estimator")
                if isinstance(values, list):
                    arr = np.stack([np.asarray(v) for v in values], axis=-1)
                else:
                    arr = np.asarray(values)
                if arr.ndim == 3:
                    importance = np.mean(np.abs(arr), axis=(0, 2))
                    local = np.mean(arr[0], axis=-1)
                elif arr.ndim == 2:
                    importance = np.mean(np.abs(arr), axis=0)
                    local = arr[0]
                else:
                    raise ValueError("Unexpected SHAP output dimensions")
                order = np.argsort(importance)[::-1][:20]
                result["feature_importance"] = {feature_names[i]: round(float(importance[i]), 6) for i in order if i < len(feature_names)}
                local_order = np.argsort(np.abs(local))[::-1][:10]
                result["local_explanation"] = {feature_names[i]: round(float(local[i]), 6) for i in local_order if i < len(feature_names)}
                result["method"] = "shap"
                result["shap_samples"] = int(len(sample))
                return result
            except Exception as exc:
                result["warnings"].append(f"SHAP unavailable; native explanation used ({type(exc).__name__}).")
        if hasattr(estimator, "feature_importances_"):
            vals = np.asarray(estimator.feature_importances_)
            result["method"] = "native_feature_importance"
        elif hasattr(estimator, "coef_"):
            vals = np.asarray(estimator.coef_)
            if vals.ndim > 1:
                vals = np.mean(np.abs(vals), axis=0)
            else:
                vals = np.abs(vals)
            result["method"] = "native_coefficient_magnitude"
        else:
            result["warnings"].append("This estimator has no supported native explanation method.")
            return result
        order = np.argsort(np.abs(vals))[::-1][:20]
        result["feature_importance"] = {feature_names[i]: round(float(vals[i]), 6) for i in order if i < len(feature_names)}
        result["local_explanation"] = {"note": "Install/enable SHAP for per-row additive contribution explanations."}
        return result
