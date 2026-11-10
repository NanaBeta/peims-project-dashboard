"""Navigation-first PEIMS experience helpers (fictional data only).

Pure functions avoid coupling page-content decisions to Streamlit. No network or storage.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

import pandas as pd


@dataclass(frozen=True)
class HomeChoice:
    target: str
    label: str
    summary: str
    icon: str


HOME_CHOICES = (
    HomeChoice("Schedule", "Manage schedule", "Activities, milestones and progress", "📅"),
    HomeChoice("Cost control", "Review costs", "Budget, expenditure and forecasts", "◈"),
    HomeChoice("Procurement", "Track deliveries", "Orders, suppliers and late equipment", "▤"),
    HomeChoice("Risks & actions", "Resolve issues", "Actions, risks and responsible owners", "⚑"),
    HomeChoice("Documents", "Open documents", "Drawings, revisions and approvals", "▦"),
    HomeChoice("Reports", "Prepare a report", "A draft report from project records", "▧"),
    HomeChoice("Spreadsheet studio", "Open spreadsheets", "Editable registers, Excel exchange and report builder", "▦"),
)


def home_choice_counts(result: dict, workflows: dict) -> dict[str, str]:
    """Show grounded project counts, never invented status or health scores."""
    k = result["kpi"]
    pid = str(result["info"]["project_id"])
    docs = workflows.get("documents", pd.DataFrame(columns=["project_id"]))
    n_docs = len(docs.loc[docs["project_id"].astype(str).eq(pid)])
    return {
        "Schedule": f'{len(result["activities"])} activities',
        "Cost control": f'{result["info"]["currency"]} budget view',
        "Procurement": f'{int(k["overdue_po"])} overdue deliveries',
        "Risks & actions": f'{int(k["overdue_actions"])} overdue actions',
        "Documents": f'{n_docs} documents',
        "Reports": "Weekly project summary",
        "Spreadsheet studio": "9 project worksheets",
    }


def priority_actions(result: dict, limit: int = 3) -> pd.DataFrame:
    """Prioritize open actions by date/priority relative to the *project snapshot*."""
    df = result["actions"].copy()
    if df.empty:
        return df
    df = df.loc[~df["status"].astype(str).str.casefold().isin(["closed", "completed"])].copy()
    if df.empty:
        return df
    df["due_date"] = pd.to_datetime(df["due_date"])
    df["_rank"] = df["priority"].astype(str).str.casefold().map({"critical": 0, "high": 1, "medium": 2, "low": 3}).fillna(4)
    if "overdue" not in df.columns:
        df["overdue"] = df["due_date"] < pd.Timestamp(result["date"])
    return df.sort_values(["overdue", "_rank", "due_date"], ascending=[False, True, True]).head(limit).drop(columns=["_rank"])


def activity_status(row) -> str:
    actual = float(row["actual_pct"])
    gap = float(row["variance_pp"])
    if actual >= 100:
        return "Completed"
    if gap < -10:
        return "Behind baseline"
    if bool(row.get("is_late", False)):
        return "Past finish date"
    return "In progress" if actual > 0 else "Not started"


def render_welcome(project: dict, kpi: dict) -> str:
    """Escaped low-density Home header with real snapshot metrics."""
    name = escape(str(project.get("project_name", "Project")))
    date = escape(str(project.get("display_date", "—")))
    actual = max(0., min(100., float(kpi.get("actual_pct", 0) or 0)))
    planned = max(0., min(100., float(kpi.get("planned_pct", 0) or 0)))
    gap = float(kpi.get("progress_gap", 0) or 0)
    return f'''<section class="peims-welcome" aria-label="Welcome to project workspace">
      <div class="peims-welcome-copy"><span class="peims-eyebrow">YOUR PROJECT WORKSPACE</span>
        <h1>Ready to move things forward?</h1>
        <p>{name} · Reporting snapshot {date}. Choose what you'd like to work on.</p>
      </div>
      <div class="peims-welcome-progress"><span class="peims-progress-label">Physical completion</span>
        <strong>{actual:.1f}%</strong>
        <div class="peims-progress" role="progressbar" aria-label="Physical completion"
          aria-valuemin="0" aria-valuemax="100" aria-valuenow="{actual:.1f}">
          <span style="width:{actual:.1f}%"></span>
          <i class="peims-progress-target" aria-hidden="true" style="left:{planned:.1f}%"></i>
        </div>
        <div class="peims-welcome-caption">Baseline {planned:.1f}% · Gap {gap:+.1f} percentage points</div>
      </div>
    </section>'''
