"""Explicit, explainable group-and-filter analytics, not Power BI compatibility.

No user-defined Python, SQL, or expression evaluation. A small allowed metric
catalog makes the analysis reproducible and safe for a public demonstration.
"""
from __future__ import annotations

import pandas as pd

SOURCE_SPECS = {
    "Activities": {
        "dimensions": ("owner", "wbs"),
        "metrics": ("Work packages", "Baseline budget", "Actual expenditure", "Earned value", "Weighted completion (%)"),
    },
    "Procurement": {
        "dimensions": ("supplier", "status", "critical"),
        "metrics": ("Purchase orders", "Order value", "Overdue orders"),
    },
    "Actions": {
        "dimensions": ("owner", "priority", "status"),
        "metrics": ("Action items", "Overdue actions"),
    },
    "Risks": {
        "dimensions": ("category", "level", "owner"),
        "metrics": ("Risks", "Open risks", "Risk score sum"),
    },
}


def source_frame(result: dict, source: str) -> pd.DataFrame:
    if source not in SOURCE_SPECS:
        raise ValueError("Unknown analytical dataset")
    mapping = {"Activities": "activities", "Procurement": "procurement",
               "Actions": "actions", "Risks": "risks"}
    return result[mapping[source]].copy()


def build_analysis(result: dict, source: str, dimension: str, metric: str,
                   filter_column: str | None = None, filter_value: str | None = None,
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    if source not in SOURCE_SPECS:
        raise ValueError("Unknown source")
    spec = SOURCE_SPECS[source]
    if dimension not in spec["dimensions"] or metric not in spec["metrics"]:
        raise ValueError("Unsupported analysis dimension or metric")
    df = source_frame(result, source)
    if filter_column is not None:
        if filter_column not in spec["dimensions"]:
            raise ValueError("Unsupported filter field")
        df = df.loc[df[filter_column].fillna("(blank)").astype(str).eq(str(filter_value))].copy()
    if df.empty:
        return pd.DataFrame(columns=[dimension, metric]), df
    df[dimension] = df[dimension].fillna("(blank)").astype(str)
    grouping = df.groupby(dimension, dropna=False, sort=True)
    if metric in {"Work packages", "Purchase orders", "Action items", "Risks"}:
        summary = grouping.size().rename(metric)
    elif metric == "Baseline budget":
        summary = grouping["baseline_budget"].sum().rename(metric)
    elif metric == "Actual expenditure":
        summary = grouping["actual_cost"].sum().rename(metric)
    elif metric == "Earned value":
        summary = grouping["earned_value"].sum().rename(metric)
    elif metric == "Weighted completion (%)":
        # Weighted by the same work-package weights as the project's overview,
        # not an unweighted average of physical completion percentages.
        numerator = (df["weight"] * df["actual_pct"]).groupby(df[dimension]).sum()
        denom = grouping["weight"].sum()
        summary = (numerator / denom.where(denom.ne(0))).fillna(0).round(1).rename(metric)
    elif metric == "Order value":
        summary = grouping["po_value"].sum().rename(metric)
    elif metric == "Overdue orders":
        summary = grouping["overdue"].sum().rename(metric)
    elif metric == "Overdue actions":
        summary = grouping["overdue"].sum().rename(metric)
    elif metric == "Open risks":
        summary = grouping["open"].sum().rename(metric)
    elif metric == "Risk score sum":
        summary = grouping["score"].sum().rename(metric)
    else:
        raise ValueError("Metric not implemented")
    summary = summary.reset_index().sort_values(metric, ascending=False, kind="stable").reset_index(drop=True)
    return summary, df
