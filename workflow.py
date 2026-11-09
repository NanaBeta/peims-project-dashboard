"""PEIMS v0.3 session-only engineering workflow registers.

No server-side user data is stored; no authentication or durable audit log is provided.
CSV snapshots are intended for fictional demo data only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import re
from zipfile import ZIP_DEFLATED, ZipFile, BadZipFile

import pandas as pd

WORKFLOW_COLUMNS: dict[str, list[str]] = {
    "contractors": ["contractor_id", "project_id", "company", "scope", "lead", "status", "planned_finish", "progress_pct", "notes"],
    "rfis": ["rfi_id", "project_id", "subject", "discipline", "raised_by", "assigned_to", "opened_on", "due_date", "status", "critical", "response_summary"],
    "documents": ["document_id", "project_id", "title", "discipline", "revision", "status", "owner", "updated_on", "document_type", "reference", "notes"],
}

DATE_COLUMNS = {
    "contractors": ("planned_finish",),
    "rfis": ("opened_on", "due_date"),
    "documents": ("updated_on",),
}
PRIMARY_KEYS = {"contractors": "contractor_id", "rfis": "rfi_id", "documents": "document_id"}
STATUSES = {
    "contractors": {"Active", "At Risk", "Complete", "On Hold"},
    "rfis": {"Open", "In Review", "Answered", "Closed"},
    "documents": {"Draft", "For Review", "Approved", "Superseded"},
}
REQUIRED_TEXT = {
    "contractors": ("company", "scope", "lead"),
    "rfis": ("subject", "discipline", "raised_by", "assigned_to"),
    "documents": ("title", "discipline", "revision", "owner", "document_type"),
}
MAX_SNAPSHOT_SIZE = 8 * 1024 * 1024


def validate_workflow(name: str, frame: pd.DataFrame, valid_projects: set[str] | None = None) -> pd.DataFrame:
    """Validate all rows, including IDs, dates, numeric bounds and project links."""
    if name not in WORKFLOW_COLUMNS:
        raise ValueError(f"Unknown register: {name}")
    columns = WORKFLOW_COLUMNS[name]
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{name}: missing fields: {', '.join(sorted(missing))}")
    if len(frame) > 3000:
        raise ValueError("A demonstration register cannot exceed 3000 rows")
    df = frame[columns].copy().reset_index(drop=True)
    for field in columns:
        if field not in DATE_COLUMNS[name] and field != "progress_pct":
            df[field] = df[field].fillna("").astype(str).str.strip()
            if df[field].str.len().gt(1000).any():
                raise ValueError(f"{name}: {field} exceeds 1000 characters")
    pk = PRIMARY_KEYS[name]
    if df[pk].eq("").any() or not df[pk].str.fullmatch(r"[A-Za-z0-9_-]{1,48}").all():
        raise ValueError(f"{name}: IDs must have 1–48 letters, numbers, hyphens or underscores")
    if df[pk].duplicated().any():
        raise ValueError(f"{name}: duplicate {pk}")
    if df["project_id"].eq("").any():
        raise ValueError(f"{name}: project ID is required")
    if valid_projects is not None and not df["project_id"].isin(valid_projects).all():
        raise ValueError(f"{name}: one or more project IDs are unknown")
    for field in REQUIRED_TEXT[name]:
        if df[field].eq("").any():
            raise ValueError(f"{name}: {field} must not be blank")
    if not df["status"].isin(STATUSES[name]).all():
        raise ValueError(f"{name}: status is not allowed")
    for field in DATE_COLUMNS[name]:
        df[field] = pd.to_datetime(df[field], errors="coerce").dt.normalize()
        if df[field].isna().any():
            raise ValueError(f"{name}: valid {field} required (YYYY-MM-DD)")
    if name == "contractors":
        df["progress_pct"] = pd.to_numeric(df["progress_pct"], errors="coerce")
        if df["progress_pct"].isna().any() or not df["progress_pct"].between(0, 100).all():
            raise ValueError("Contractor progress must be between 0 and 100")
    if name == "rfis":
        if (df["due_date"] < df["opened_on"]).any():
            raise ValueError("RFI due date cannot precede its open date")
        if not df["critical"].isin({"Yes", "No"}).all():
            raise ValueError("RFI critical flag must be Yes or No")
    return df


def workflow_metrics(tables: dict[str, pd.DataFrame], project_id: str, snapshot_date) -> dict:
    date = pd.Timestamp(snapshot_date).normalize()
    c = tables["contractors"].loc[tables["contractors"]["project_id"].eq(project_id)]
    r = tables["rfis"].loc[tables["rfis"]["project_id"].eq(project_id)]
    d = tables["documents"].loc[tables["documents"]["project_id"].eq(project_id)]
    pending = r["status"].isin(["Open", "In Review"])
    return {
        "contractors": len(c),
        "at_risk_contractors": int((c["status"] == "At Risk").sum()),
        "overdue_contractors": int(((c["planned_finish"] < date) & (~c["status"].eq("Complete"))).sum()),
        "pending_rfis": int(pending.sum()),
        "overdue_rfis": int((pending & (r["due_date"] < date)).sum()),
        "critical_open_rfis": int((pending & r["critical"].eq("Yes")).sum()),
        "documents": len(d),
        "pending_documents": int(d["status"].eq("For Review").sum()),
    }


def normalize_for_export(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in result.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns:
        result[col] = result[col].dt.strftime("%Y-%m-%d")
    return result


def apply_project_register(name: str, original: pd.DataFrame, editable: pd.DataFrame,
                           project_id: str, valid_projects: set[str], actor: str = "demo_session") -> tuple[pd.DataFrame, list[dict]]:
    """Replace the selected project's rows; preserve other projects and create session events."""
    columns = WORKFLOW_COLUMNS[name]
    changed = editable.copy()
    changed["project_id"] = project_id  # never trust a project field provided by a form
    changed = validate_workflow(name, changed, valid_projects)
    remainder = original.loc[~original["project_id"].eq(project_id), columns].copy()
    combined = validate_workflow(name, pd.concat([remainder, changed], ignore_index=True), valid_projects)
    original_project = original.loc[original["project_id"].eq(project_id)].copy()
    key = PRIMARY_KEYS[name]
    before = {str(row[key]): row for _, row in original_project.iterrows()}
    after = {str(row[key]): row for _, row in changed.iterrows()}
    actions = []
    for rid in sorted(before.keys() | after.keys()):
        if rid not in before:
            action = "created"
        elif rid not in after:
            action = "deleted"
        else:
            old = {k: str(v) for k, v in before[rid].items()}
            new = {k: str(v) for k, v in after[rid].items()}
            if old == new:
                continue
            action = "updated"
        actions.append({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "actor": actor, "project_id": project_id, "register": name,
            "record_id": rid, "action": action,
        })
    return combined, actions


def workflow_report_appendix(workflows: dict[str, pd.DataFrame], project_id: str, snapshot_date) -> str:
    """Transparent, deterministic management-summary appendix; not AI-generated."""
    m = workflow_metrics(workflows, project_id, snapshot_date)
    overdue = workflows["rfis"].loc[
        workflows["rfis"]["project_id"].eq(project_id)
        & workflows["rfis"]["status"].isin(["Open", "In Review"])
        & (workflows["rfis"]["due_date"] < pd.Timestamp(snapshot_date))
    ]
    at_risk = workflows["contractors"].loc[
        workflows["contractors"]["project_id"].eq(project_id)
        & workflows["contractors"]["status"].eq("At Risk")
    ]
    ids = ", ".join(overdue["rfi_id"].astype(str).tolist()) or "None"
    names = ", ".join(at_risk["company"].astype(str).tolist()) or "None"
    return ("\n\n## Engineering workflow summary (demo)\n"
            f"- Active RFIs: **{m['pending_rfis']}**, including **{m['overdue_rfis']}** overdue and "
            f"**{m['critical_open_rfis']}** marked critical.\n"
            f"- Overdue RFI references: {ids}.\n"
            f"- At-risk contractors: **{m['at_risk_contractors']}** — {names}.\n"
            f"- Documents awaiting review: **{m['pending_documents']}**.\n\n"
            "This section is assembled from fictional register records; verify with authorized project controls.\n")


def make_snapshot(core: dict[str, pd.DataFrame], workflows: dict[str, pd.DataFrame],
                  audit: list[dict], core_names: list[str]) -> bytes:
    """User-downloaded ZIP: not automatic cloud persistence."""
    bio = BytesIO()
    with ZipFile(bio, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps({"app": "PEIMS", "version": "0.3", "mode": "session-backup",
             "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=2))
        for name in core_names:
            z.writestr(f"core/{name}.csv", normalize_for_export(core[name]).to_csv(index=False))
        for name in WORKFLOW_COLUMNS:
            z.writestr(f"workflows/{name}.csv", normalize_for_export(workflows[name]).to_csv(index=False))
        if audit:
            z.writestr("session_history.csv", pd.DataFrame(audit).to_csv(index=False))
    return bio.getvalue()


def read_snapshot(payload: bytes, core_names: list[str], core_validator, core_compute,
                  project_selector) -> tuple[dict, dict, list[dict]]:
    """Validate an untrusted ZIP and all project dependencies before changing app state."""
    if len(payload) > MAX_SNAPSHOT_SIZE:
        raise ValueError("Backup exceeds the 8 MB demonstration limit")
    expected = {f"core/{n}.csv" for n in core_names} | {f"workflows/{n}.csv" for n in WORKFLOW_COLUMNS}
    try:
        with ZipFile(BytesIO(payload)) as z:
            members = z.infolist()
            names = set(z.namelist())
            if len(members) != len(names):
                raise ValueError("Duplicate files in snapshot")
            if sum(v.file_size for v in members) > MAX_SNAPSHOT_SIZE:
                raise ValueError("Uncompressed snapshot exceeds size limit")
            if not expected.issubset(names) or "manifest.json" not in names:
                raise ValueError("Missing required snapshot datasets")
            if names - (expected | {"manifest.json", "session_history.csv"}):
                raise ValueError("Unexpected files inside snapshot")
            if any(v.file_size > MAX_SNAPSHOT_SIZE for v in z.infolist()):
                raise ValueError("Snapshot member exceeds size limit")
            manifest = json.loads(z.read("manifest.json"))
            if manifest.get("app") != "PEIMS" or manifest.get("version") != "0.3":
                raise ValueError("Unsupported PEIMS snapshot")
            core = {n: core_validator(n, pd.read_csv(BytesIO(z.read(f"core/{n}.csv")))) for n in core_names}
            projects = set(core["projects"]["project_id"].astype(str))
            workflows = {n: validate_workflow(n, pd.read_csv(BytesIO(z.read(f"workflows/{n}.csv"))), projects)
                         for n in WORKFLOW_COLUMNS}
            history = []
            if "session_history.csv" in names:
                audit_frame = pd.read_csv(BytesIO(z.read("session_history.csv"))).fillna("")
                allowed = ["timestamp_utc", "actor", "project_id", "register", "record_id", "action"]
                if set(allowed) != set(audit_frame.columns) or len(audit_frame) > 250:
                    raise ValueError("Session history format is invalid")
                history = audit_frame[allowed].astype(str).to_dict("records")
    except (BadZipFile, UnicodeDecodeError, KeyError) as e:
        raise ValueError("Invalid or corrupted PEIMS snapshot") from e
    for pid in projects:
        core_compute(project_selector(core, pid))
    return core, workflows, history
