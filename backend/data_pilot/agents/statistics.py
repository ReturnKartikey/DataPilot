"""Assumption-aware descriptive and basic inferential statistics."""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from scipy import stats


class StatisticalAnalysisAgent:
    def analyze(self, df: pd.DataFrame, target_column: str | None = None) -> dict:
        numeric = df.select_dtypes(include=np.number)
        output = {"status": "success", "descriptive": {}, "tests": [], "notes": []}
        if not numeric.empty:
            desc = numeric.describe(percentiles=[.25, .5, .75]).T
            desc["variance"] = numeric.var(numeric_only=True)
            desc["skewness"] = numeric.skew(numeric_only=True)
            desc["kurtosis"] = numeric.kurtosis(numeric_only=True)
            output["descriptive"] = desc.replace([np.inf, -np.inf], np.nan).where(pd.notna(desc), None).round(5).to_dict(orient="index")
            output["correlation"] = numeric.corr().replace([np.inf, -np.inf], np.nan).where(pd.notna(numeric.corr()), None).round(5).to_dict()
        else:
            output["notes"].append("No numeric columns available for descriptive statistics.")
        # A conservative two-group numeric-vs-binary-target Welch t-test only.
        if target_column and target_column in df.columns:
            groups = df[target_column].dropna().unique()
            if len(groups) == 2:
                for column in numeric.columns[:20]:
                    if column == target_column:
                        continue
                    left = pd.to_numeric(df.loc[df[target_column] == groups[0], column], errors="coerce").dropna()
                    right = pd.to_numeric(df.loc[df[target_column] == groups[1], column], errors="coerce").dropna()
                    if len(left) >= 3 and len(right) >= 3:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            stat, p = stats.ttest_ind(left, right, equal_var=False, nan_policy="omit")
                        if np.isfinite(stat) and np.isfinite(p):
                            output["tests"].append({"test": "welch_t_test", "feature": str(column), "groups": [str(groups[0]), str(groups[1])], "statistic": float(stat), "p_value": float(p), "interpretation": "Evidence of a difference at alpha=0.05" if p < .05 else "No statistically significant difference at alpha=0.05", "caution": "Associational test; does not establish causation."})
                            mw_stat, mw_p = stats.mannwhitneyu(left, right, alternative="two-sided")
                            if np.isfinite(mw_stat) and np.isfinite(mw_p):
                                output["tests"].append({"test": "mann_whitney_u", "feature": str(column), "groups": [str(groups[0]), str(groups[1])], "statistic": float(mw_stat), "p_value": float(mw_p), "interpretation": "Evidence of a distribution/rank difference at alpha=0.05" if mw_p < .05 else "No significant rank-distribution difference at alpha=0.05", "assumption_note": "Independent samples; non-parametric alternative to a two-sample t-test."})
                        else:
                            output["notes"].append(f"Welch t-test skipped for {column}: degenerate or non-finite group values.")
            elif 2 < len(groups) <= 10:
                output["notes"].append("The selected target is not binary; multiclass ANOVA and rank-based tests are used when group sample sizes permit.")
                for column in numeric.columns[:20]:
                    if column == target_column: continue
                    samples=[pd.to_numeric(df.loc[df[target_column] == group, column], errors="coerce").dropna() for group in groups]
                    samples=[sample for sample in samples if len(sample)>=3]
                    if len(samples)==len(groups):
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            stat,p=stats.f_oneway(*samples)
                        if np.isfinite(stat) and np.isfinite(p):
                            output["tests"].append({"test":"one_way_anova","feature":str(column),"groups":[str(x) for x in groups],"statistic":float(stat),"p_value":float(p),"interpretation":"At least one group mean differs at alpha=0.05" if p<.05 else "No significant group mean difference at alpha=0.05","assumption_note":"Independent observations and approximately normal residuals; check homogeneity of variance."})
                            # Non-parametric companion test for robustness.
                            h,pm=stats.kruskal(*samples)
                            if np.isfinite(h) and np.isfinite(pm): output["tests"].append({"test":"kruskal_wallis","feature":str(column),"statistic":float(h),"p_value":float(pm),"interpretation":"At least one group distribution differs at alpha=0.05" if pm<.05 else "No significant distribution difference at alpha=0.05","assumption_note":"Independent samples; compares rank distributions."})
            else:
                output["notes"].append("Numeric group tests skipped: target has too many distinct groups or insufficient observations.")
            # Chi-square association for categorical features against a categorical target.
            if len(groups) >= 2:
                categorical=[c for c in df.select_dtypes(exclude=np.number).columns if c != target_column][:15]
                for column in categorical:
                    table=pd.crosstab(df[column].fillna("<missing>"),df[target_column].fillna("<missing>"))
                    if table.shape[0]>=2 and table.shape[1]>=2 and table.size<=2500:
                        chi2,p,dof,expected=stats.chi2_contingency(table)
                        output["tests"].append({"test":"chi_square_independence","feature":str(column),"statistic":float(chi2),"p_value":float(p),"degrees_of_freedom":int(dof),"interpretation":"Evidence of association at alpha=0.05" if p<.05 else "No significant association at alpha=0.05","assumption_note":"Expected cell counts should generally be at least 5; inspect the expected-frequency table."})
        return output
