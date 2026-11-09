"""Pure, explainable project-control calculations for the PEIMS demonstration.

No company connection, no model inference, and no external network calls.
"""
from __future__ import annotations

from datetime import date
from typing import Mapping

import pandas as pd

DATASET_COLUMNS: dict[str, list[str]] = {
    "projects": ["project_id", "project_name", "type", "location", "manager", "snapshot_date", "currency"],
    "activities": ["activity_id", "project_id", "wbs", "activity", "owner", "start_date", "finish_date", "weight", "actual_pct", "baseline_budget"],
    "costs": ["activity_id", "project_id", "actual_cost", "committed_cost"],
    "procurement": ["po_id", "project_id", "item", "supplier", "expected_date", "received_date", "po_value", "critical", "status"],
    "risks": ["risk_id", "project_id", "risk", "category", "probability", "impact", "owner", "mitigation", "status"],
    "actions": ["action_id", "project_id", "action", "owner", "due_date", "priority", "status", "source"],
    "progress_history": ["project_id", "week_ending", "planned_pct", "actual_pct"],
}


def validated_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Validate schema and common constraints to avoid silent bad KPI calculations."""
    if name not in DATASET_COLUMNS:
        raise ValueError(f"Unknown dataset: {name}")
    missing = sorted(set(DATASET_COLUMNS[name]) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(missing)}")
    df = frame[DATASET_COLUMNS[name]].copy()
    # Fail closed for blank IDs and empty required labels. Without this check,
    # imports could silently disconnect activities, costs and reporting records.
    key_columns = {
        "projects": ["project_id", "project_name", "currency"],
        "activities": ["activity_id", "project_id", "activity"],
        "costs": ["activity_id", "project_id"],
        "procurement": ["po_id", "project_id", "item", "status"],
        "risks": ["risk_id", "project_id", "risk", "status"],
        "actions": ["action_id", "project_id", "action", "status"],
        "progress_history": ["project_id"],
    }
    for col in key_columns[name]:
        if df[col].isna().any() or df[col].astype(str).str.strip().eq("").any():
            raise ValueError(f"Column {col} requires nonempty values")
    for key in ("activity_id", "po_id", "risk_id", "action_id"):
        if key in df and df[key].astype(str).duplicated().any():
            raise ValueError(f"{key} must be unique")
    for col in ["weight", "actual_pct", "baseline_budget", "actual_cost", "committed_cost", "po_value", "probability", "impact", "planned_pct"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="raise")
            if df[col].isna().any() or (df[col] < 0).any():
                raise ValueError(f"Column {col} contains null or negative numbers")
    if "actual_pct" in df and (df["actual_pct"] > 100).any():
        raise ValueError("Activity progress must be between 0 and 100")
    if name == "progress_history":
        for col in ["planned_pct", "actual_pct"]:
            if (df[col] > 100).any():
                raise ValueError("Historical progress must be between 0 and 100")
    if name == "risks":
        for col in ["probability", "impact"]:
            if (df[col] > 5).any() or (df[col] < 1).any() or (df[col] % 1 != 0).any():
                raise ValueError("Risk probability and impact must be whole numbers from 1 to 5")
    for col in ["start_date", "finish_date", "snapshot_date", "expected_date", "due_date", "week_ending"]:
        if col in df:
            df[col] = pd.to_datetime(df[col], errors="raise").dt.normalize()
            if df[col].isna().any():
                raise ValueError(f"Column {col} cannot contain blank dates")
    if "received_date" in df:
        nonblank = df["received_date"].notna() & df["received_date"].astype(str).str.strip().ne("")
        df["received_date"] = pd.to_datetime(df["received_date"], errors="coerce").dt.normalize()
        if (nonblank & df["received_date"].isna()).any():
            raise ValueError("Received date is invalid")
        received = df["status"].astype(str).str.casefold().str.strip().eq("received")
        if (received & df["received_date"].isna()).any():
            raise ValueError("Received orders require a received date")
    if name == "activities":
        if (df["finish_date"] < df["start_date"]).any():
            raise ValueError("An activity ends before it starts")
        if df["activity_id"].duplicated().any():
            raise ValueError("Activity IDs must be unique")
    if name == "costs" and df["activity_id"].duplicated().any():
        raise ValueError("Cost rows must have unique activity IDs")
    if name == "projects" and df["project_id"].duplicated().any():
        raise ValueError("Project IDs must be unique")
    if name == "progress_history" and df.duplicated(subset=["project_id", "week_ending"]).any():
        raise ValueError("Duplicate weekly snapshots for a project")
    return df


def planned_percentage(starts: pd.Series, finishes: pd.Series, snapshot: pd.Timestamp) -> pd.Series:
    """Simple linear baseline assumption, inclusive of planned start/finish days.

    For professional use replace with an approved time-phased baseline.
    """
    start = pd.to_datetime(starts)
    finish = pd.to_datetime(finishes)
    days = (finish - start).dt.days + 1
    elapsed = (snapshot - start).dt.days + 1
    return (elapsed / days * 100).clip(lower=0, upper=100).round(1)


def select_project(data: Mapping[str, pd.DataFrame], project_id: str) -> dict[str, pd.DataFrame]:
    return {key: (df.loc[df["project_id"].eq(project_id)].copy() if "project_id" in df.columns else df.copy()) for key, df in data.items()}


def compute(project: Mapping[str, pd.DataFrame]) -> dict:
    projects = project["projects"]
    if len(projects) != 1:
        raise ValueError("Exactly one project is required")
    info = projects.iloc[0].to_dict()
    snapshot = pd.Timestamp(info["snapshot_date"])
    acts = project["activities"].copy()
    if acts.empty:
        raise ValueError("At least one activity is required")
    costs = project["costs"].copy()
    if set(costs["activity_id"].astype(str)) != set(acts["activity_id"].astype(str)):
        raise ValueError("Each activity requires exactly one matching cost record; unmatched cost rows are not allowed")
    acts = acts.merge(costs, how="left", on=["activity_id", "project_id"], validate="one_to_one")
    if acts[["actual_cost", "committed_cost"]].isna().any().any():
        raise ValueError("Every activity needs a matching cost row")
    acts["planned_pct"] = planned_percentage(acts["start_date"], acts["finish_date"], snapshot)
    acts["variance_pp"] = (acts["actual_pct"] - acts["planned_pct"]).round(1)
    acts["earned_value"] = acts["baseline_budget"] * acts["actual_pct"] / 100
    acts["planned_value"] = acts["baseline_budget"] * acts["planned_pct"] / 100
    acts["is_late"] = (acts["finish_date"] < snapshot) & (acts["actual_pct"] < 100)
    acts["is_at_risk"] = (acts["variance_pp"] < -10) & (acts["actual_pct"] < 100)
    budget = float(acts["baseline_budget"].sum())
    actual_cost = float(acts["actual_cost"].sum())
    committed_cost = float(acts["committed_cost"].sum())
    earned = float(acts["earned_value"].sum())
    planned_value = float(acts["planned_value"].sum())
    weight = acts["weight"].sum()
    if weight <= 0:
        raise ValueError("Weights must sum to a positive number")
    overall_actual = float((acts["weight"] * acts["actual_pct"]).sum() / weight)
    overall_planned = float((acts["weight"] * acts["planned_pct"]).sum() / weight)
    procurement = project["procurement"].copy()
    procurement["received"] = procurement["status"].str.casefold().eq("received")
    procurement["overdue"] = (~procurement["received"]) & procurement["expected_date"].lt(snapshot)
    procurement["days_late"] = (snapshot - procurement["expected_date"]).dt.days.clip(lower=0).where(procurement["overdue"], 0)
    risks = project["risks"].copy()
    risks["score"] = risks["probability"] * risks["impact"]
    risks["open"] = risks["status"].str.casefold().eq("open")
    risks["level"] = risks["score"].apply(lambda n: "High" if n >= 15 else ("Medium" if n >= 8 else "Low"))
    actions = project["actions"].copy()
    actions["closed"] = actions["status"].str.casefold().eq("closed")
    actions["overdue"] = (~actions["closed"]) & actions["due_date"].lt(snapshot)
    hist = project["progress_history"].copy().sort_values("week_ending")
    metrics = {
        "budget": budget,
        "actual_cost": actual_cost,
        "committed_cost": committed_cost,
        "earned_value": earned,
        "planned_value": planned_value,
        "remaining_budget": budget - actual_cost,
        "cost_variance": earned - actual_cost,
        "schedule_variance_value": earned - planned_value,
        "cpi": earned / actual_cost if actual_cost else None,
        "spi": earned / planned_value if planned_value else None,
        "actual_pct": overall_actual,
        "planned_pct": overall_planned,
        "progress_gap": overall_actual - overall_planned,
        "late_activities": int(acts["is_late"].sum()),
        "slipping_activities": int(acts["is_at_risk"].sum()),
        "overdue_po": int(procurement["overdue"].sum()),
        "critical_overdue_po": int((procurement["overdue"] & procurement["critical"].astype(str).str.casefold().isin(["yes", "true", "1"])).sum()),
        "open_high_risks": int((risks["open"] & risks["level"].eq("High")).sum()),
        "overdue_actions": int(actions["overdue"].sum()),
    }
    return {"info": info, "date": snapshot, "activities": acts, "procurement": procurement, "risks": risks, "actions": actions, "history": hist, "kpi": metrics}


def make_alerts(result: dict) -> list[dict]:
    """Transparent rule-based flags, not statistical predictions or AI decisions."""
    k = result["kpi"]
    alerts = []
    if k["critical_overdue_po"]:
        alerts.append({"severity": "Critical", "area": "Procurement", "message": f"{k['critical_overdue_po']} critical-item purchase order(s) past expected delivery date.", "next": "Confirm supplier status and evaluate schedule impacts."})
    if k["late_activities"]:
        alerts.append({"severity": "High", "area": "Schedule", "message": f"{k['late_activities']} activity/activities incomplete beyond baseline finish.", "next": "Validate actual progress, dependencies, and recovery plan."})
    if k["progress_gap"] < -5:
        alerts.append({"severity": "High", "area": "Progress", "message": f"Weighted actual progress is {abs(k['progress_gap']):.1f} percentage points behind the linear baseline.", "next": "Review slipping work packages with their owners."})
    if k["cpi"] is not None and k["cpi"] < 0.95:
        alerts.append({"severity": "High", "area": "Costs", "message": f"Cost performance index is {k['cpi']:.2f}, below the 0.95 demonstration threshold.", "next": "Reconcile expenditures and earned-value inputs."})
    if k["open_high_risks"]:
        alerts.append({"severity": "High", "area": "Risk register", "message": f"{k['open_high_risks']} open risk(s) score high (15+ on the 5×5 matrix).", "next": "Review risk owners, mitigations and escalation requirements."})
    if k["overdue_actions"]:
        alerts.append({"severity": "Medium", "area": "Action tracking", "message": f"{k['overdue_actions']} action(s) have passed their due dates.", "next": "Confirm ownership and revised target dates."})
    if k["overdue_po"] and not k["critical_overdue_po"]:
        alerts.append({"severity": "Medium", "area": "Procurement", "message": f"{k['overdue_po']} purchase order(s) past expected delivery date.", "next": "Contact suppliers and update receipt forecasts."})
    if not alerts:
        alerts.append({"severity": "Info", "area": "Status", "message": "No demonstration thresholds have been exceeded.", "next": "Continue routine progress verification."})
    return alerts


def money(value: float, currency: str = "GHS") -> str:
    return f"{currency} {value:,.0f}"


def weekly_report(result: dict) -> str:
    info, k = result["info"], result["kpi"]
    date_str = result["date"].strftime("%d %B %Y")
    c = info["currency"]
    lines = [
        f"# PEIMS | Weekly Project Controls Report",
        "", f"**Project:** {info['project_name']}",
        f"**Reporting snapshot:** {date_str}",
        f"**Location:** {info['location']}",
        "**Data classification:** FICTIONAL DEMONSTRATION DATA — not an official mine report",
        "", "## Executive overview",
        f"- Weighted physical progress: **{k['actual_pct']:.1f}%** actual vs **{k['planned_pct']:.1f}%** baseline (gap **{k['progress_gap']:+.1f} percentage points**).",
        f"- Approved baseline budget: **{money(k['budget'], c)}**; recorded actual costs: **{money(k['actual_cost'], c)}**.",
        f"- Earned value (EV): **{money(k['earned_value'], c)}**; planned value (PV): **{money(k['planned_value'], c)}**.",
        f"- CPI: **{k['cpi']:.2f}**; SPI: **{k['spi']:.2f}**." if k["cpi"] is not None and k["spi"] is not None else "- CPI/SPI: not computable from current records.",
        "", "## Priority flags (rule-based)",
    ]
    for item in make_alerts(result):
        lines.append(f"- **{item['severity']} | {item['area']}** — {item['message']} **Suggested follow-up:** {item['next']}")
    lines.extend(["", "## Activities requiring attention"])
    problem_activities = result["activities"].loc[lambda df: df["is_at_risk"] | df["is_late"]].sort_values("variance_pp")
    if problem_activities.empty:
        lines.append("- None flagged by demonstration rules.")
    else:
        for _, a in problem_activities.head(8).iterrows():
            lines.append(f"- {a['activity_id']} — {a['activity']}: {a['actual_pct']:.0f}% actual vs {a['planned_pct']:.0f}% planned ({a['variance_pp']:+.1f} pp); owner {a['owner']}.")
    lines.extend(["", "## Critical deliveries outstanding"])
    late = result["procurement"].loc[lambda df: df["overdue"]].sort_values("days_late", ascending=False)
    if late.empty:
        lines.append("- No overdue orders in the imported records.")
    else:
        for _, po in late.head(8).iterrows():
            lines.append(f"- {po['po_id']} — {po['item']}: {int(po['days_late'])} day(s) past expected date; critical={po['critical']}.")
    lines.extend(["", "## Open high risks and overdue actions"])
    high = result["risks"].loc[lambda df: df["open"] & df["level"].eq("High")].sort_values("score", ascending=False)
    for _, item in high.head(6).iterrows():
        lines.append(f"- Risk {item['risk_id']} (score {int(item['score'])}): {item['risk']} — {item['mitigation']}")
    overdue = result["actions"].loc[lambda df: df["overdue"]].sort_values("due_date")
    for _, item in overdue.head(6).iterrows():
        lines.append(f"- Overdue action {item['action_id']}: {item['action']} (owner: {item['owner']}).")
    if high.empty and overdue.empty:
        lines.append("- None flagged.")
    lines += ["", "## Methodology and caveats", 
              "- Planned physical progress assumes linear completion between each activity's baseline start and finish; production schedules normally require approved time-phased progress curves.",
              "- Overall physical progress is weighted by activity weight, while EV and PV are weighted by baseline budget; these measures can differ.",
              "- EV = sum(activity budget × actual completion fraction). PV = sum(activity budget × planned completion fraction). AC = sum recorded actual costs.",
              "- CPI = EV / AC and SPI = EV / PV. These ratios depend on the accuracy of input progress and cost records.",
              "- Alerts are deterministic threshold checks, not AI predictions or safety approvals.",
              "- Verify data, field conditions, controls and decisions with authorized personnel before any operational use.", ""]
    return "\n".join(lines)
