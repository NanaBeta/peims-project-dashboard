"""Limited, explainable schedule-network and commercial forecasts for fictional PEIMS projects.

Scheduling assumes calendar days, finish-to-start links, non-negative lags and earliest
start constraints from each activity's recorded baseline start. It is NOT a P6 engine.
"""
from __future__ import annotations
from collections import deque
from datetime import timedelta
from typing import Mapping
import pandas as pd

REQUIRED_LINKS = ("project_id", "predecessor_id", "successor_id", "lag_days")


def critical_path(activities: pd.DataFrame, dependencies: pd.DataFrame) -> dict:
    """Compute a dependency-constrained schedule and total float for one project.

    Dates are inclusive calendar days; all dependencies are finish-to-start, meaning
    successor earliest start >= predecessor earliest finish + 1 + lag_days.
    Uses the baseline activity start as a not-before constraint (not an actual forecast).
    """
    if activities.empty:
        raise ValueError("At least one activity is required")
    if any(c not in activities.columns for c in ("activity_id", "start_date", "finish_date")):
        raise ValueError("Activity columns are missing")
    for c in REQUIRED_LINKS:
        if c not in dependencies.columns:
            raise ValueError(f"Missing dependency column {c}")
    acts = activities.copy()
    acts["activity_id"] = acts["activity_id"].astype(str)
    if acts["activity_id"].duplicated().any():
        raise ValueError("Duplicate activity ID")
    acts["start_date"] = pd.to_datetime(acts["start_date"]).dt.normalize()
    acts["finish_date"] = pd.to_datetime(acts["finish_date"]).dt.normalize()
    if (acts["finish_date"] < acts["start_date"]).any():
        raise ValueError("Finish before start")
    ids = set(acts["activity_id"])
    start_dates = dict(zip(acts["activity_id"], acts["start_date"]))
    durations = dict(zip(acts["activity_id"], (acts["finish_date"] - acts["start_date"]).dt.days + 1))
    pred = {x: [] for x in ids}
    succ = {x: [] for x in ids}
    seen = set()
    for row in dependencies.to_dict("records"):
        u, v = str(row["predecessor_id"]), str(row["successor_id"])
        if u not in ids or v not in ids:
            raise ValueError("Dependency references unknown or cross-project activity")
        if u == v or (u, v) in seen:
            raise ValueError("Self-link or duplicate dependency")
        seen.add((u, v))
        lag_float = float(row["lag_days"])
        if lag_float != int(lag_float) or lag_float < 0:
            raise ValueError("Only nonnegative whole-day lags supported")
        lag = int(lag_float)
        pred[v].append((u, lag))
        succ[u].append((v, lag))
    waiting = {v: len(pred[v]) for v in ids}
    q = deque(sorted((v for v in ids if not waiting[v])))
    topo = []
    while q:
        u = q.popleft()
        topo.append(u)
        for v, _ in succ[u]:
            waiting[v] -= 1
            if waiting[v] == 0:
                q.append(v)
    if len(topo) != len(ids):
        raise ValueError("Dependency network contains a cycle")
    earliest_start, earliest_finish = {}, {}
    for v in topo:
        candidate = [start_dates[v]] + [earliest_finish[u] + timedelta(days=lag+1) for u, lag in pred[v]]
        earliest_start[v] = max(candidate)
        earliest_finish[v] = earliest_start[v] + timedelta(days=int(durations[v])-1)
    finish_date = max(earliest_finish.values())
    latest_start, latest_finish = {}, {}
    for v in reversed(topo):
        latest_finish[v] = (min(latest_start[u]-timedelta(days=lag+1) for u,lag in succ[v])
                            if succ[v] else finish_date)
        latest_start[v] = latest_finish[v] - timedelta(days=int(durations[v])-1)
    lines = []
    for v in topo:
        slack = int((latest_start[v] - earliest_start[v]).days)
        lines.append({"activity_id": v, "earliest_start": str(earliest_start[v].date()),
                      "earliest_finish": str(earliest_finish[v].date()),
                      "total_float_days": slack, "critical": slack == 0,
                      "duration_days": int(durations[v])})
    return {"project_start": str(min(earliest_start.values()).date()),
            "model_finish": str(finish_date.date()),
            "critical_activity_ids": [r["activity_id"] for r in lines if r["critical"]],
            "activities": lines,
            "assumptions": "Finish-to-start calendar-day links, nonnegative lag, baseline not-before starts; no resource leveling or actual progress rescheduling."}


def cost_forecast(budget: float, earned_value: float, actual_cost: float, commitments: float = 0.0) -> dict:
    """Simple CPI continuation forecast; commitments separately disclosed, never added to AC."""
    vals = [float(v) for v in (budget, earned_value, actual_cost, commitments)]
    if any(v < 0 for v in vals):
        raise ValueError("Cost inputs must be nonnegative")
    bac, ev, ac, commits = vals
    if bac <= 0 or ev > bac + 0.01:
        raise ValueError("BAC must be positive and EV cannot exceed BAC")
    cpi = ev / ac if ac > 0 else None
    # Avoid pretending forecast can be computed before any verified performance exists.
    eac = (ac + (bac-ev)/cpi) if cpi and cpi > 0 else None
    etc = (eac - ac) if eac is not None else None
    vac = (bac - eac) if eac is not None else None
    return {"bac": bac, "ev": ev, "ac": ac, "cpi": cpi, "eac_cpi": eac,
            "etc_cpi": etc, "vac_cpi": vac, "commitments_unspent": commits,
            "method": "EAC = AC + (BAC−EV)/CPI; scenario only, assumes future CPI equals observed CPI."}
