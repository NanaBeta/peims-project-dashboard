"""Safe, project-scoped spreadsheet interoperability for the fictional PEIMS demo.

No Excel formulas are executed, no persistent database is used, and imports cannot
rewrite other projects or silently change existing record identifiers. Core validators
and project-control calculations are the source of truth.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import re
from zipfile import BadZipFile, ZipFile

import pandas as pd

from analytics import DATASET_COLUMNS, compute, select_project, validated_frame
from workflow import WORKFLOW_COLUMNS, PRIMARY_KEYS, apply_project_register, normalize_for_export

SHEET_NAMES = (
    "activities", "costs", "procurement", "actions", "risks",
    "contractors", "rfis", "documents", "progress_history",
)
EDITABLE_SHEETS = frozenset(SHEET_NAMES) - {"progress_history"}
SHEET_LABELS = {
    "activities": "Activities & WBS", "costs": "Cost ledger",
    "procurement": "Procurement orders", "actions": "Action register",
    "risks": "Risk register", "contractors": "Contractors",
    "rfis": "Requests for information", "documents": "Document register",
    "progress_history": "Progress snapshots (read-only)",
}
SHEET_KEYS = {
    "activities": "activity_id", "costs": "activity_id", "procurement": "po_id",
    "actions": "action_id", "risks": "risk_id", "contractors": "contractor_id",
    "rfis": "rfi_id", "documents": "document_id",
    "progress_history": "week_ending",
}
MAX_XLSX_BYTES = 4 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 24 * 1024 * 1024
MAX_SHEET_ROWS = 3000


def project_sheet(core: dict, workflows: dict, sheet: str, project_id: str) -> pd.DataFrame:
    if sheet not in SHEET_NAMES:
        raise ValueError(f"Unknown PEIMS worksheet: {sheet}")
    source = core if sheet in DATASET_COLUMNS else workflows
    df = source[sheet]
    return df.loc[df["project_id"].astype(str).eq(project_id)].copy().reset_index(drop=True)


def _canonical(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()[:10]
    return str(value).strip()


def _change_events(before: pd.DataFrame, after: pd.DataFrame, key: str,
                   sheet: str, project_id: str) -> list[dict]:
    first = before.set_index(key)
    second = after.set_index(key)
    events = []
    for rid in second.index.difference(first.index):
        events.append({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "actor": "demo_session", "project_id": project_id,
            "register": sheet, "record_id": str(rid), "action": "created",
            "fields": ", ".join(col for col in second.columns if col != "project_id"),
        })
    for rid in first.index:
        modified = [col for col in first.columns if col in second.columns and
                    _canonical(first.at[rid, col]) != _canonical(second.at[rid, col])]
        if modified:
            events.append({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "actor": "demo_session", "project_id": project_id,
                "register": sheet, "record_id": str(rid), "action": "updated",
                "fields": ", ".join(modified),
            })
    return events


def apply_sheet(core: dict[str, pd.DataFrame], workflows: dict[str, pd.DataFrame],
                sheet: str, project_id: str, edited: pd.DataFrame
                ) -> tuple[dict, dict, list[dict]]:
    """Validate a whole edited sheet atomically, retaining all other project rows."""
    if sheet not in EDITABLE_SHEETS:
        raise ValueError("Worksheet is read-only or unsupported")
    expected = WORKFLOW_COLUMNS.get(sheet, DATASET_COLUMNS.get(sheet))
    if expected is None or not set(expected).issubset(edited.columns):
        raise ValueError(f"Sheet must contain the original columns: {', '.join(expected or [])}")
    if len(edited) > MAX_SHEET_ROWS:
        raise ValueError("Spreadsheet exceeds demonstration row limit")
    proposed = edited.loc[:, expected].copy().reset_index(drop=True)
    original = project_sheet(core, workflows, sheet, project_id)
    key = SHEET_KEYS[sheet]
    # Existing record identities cannot be renamed or deleted from a worksheet.
    # New records are supported where project-control invariants allow them.
    if project_id not in set(core["projects"]["project_id"].astype(str)):
        raise ValueError("Unknown project")
    original_ids = set(original[key].astype(str))
    if proposed[key].isna().any() or proposed[key].astype(str).str.strip().eq("").any():
        raise ValueError(f"Every added row needs a unique {key}; please fill its ID")
    proposed[key] = proposed[key].astype(str).str.strip()
    if proposed[key].duplicated().any():
        raise ValueError(f"Duplicate {key}; enter a unique identifier for every row")
    after_ids = set(proposed[key])
    if not original_ids.issubset(after_ids):
        raise ValueError("Existing record IDs cannot be deleted or renamed in Spreadsheet Studio")
    new_ids = after_ids - original_ids
    if sheet == "costs" and new_ids:
        raise ValueError("New cost rows are created automatically when you add an activity. Edit those rows in Cost ledger.")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", rid) for rid in new_ids):
        raise ValueError("New record IDs need 1–48 letters, digits, hyphens or underscores")

    # The project field for added grid rows is filled by PEIMS; the project
    # field of existing rows cannot be modified, and foreign projects are refused.
    old_rows = proposed[key].isin(original_ids)
    if not proposed.loc[old_rows, "project_id"].astype(str).eq(project_id).all():
        raise ValueError("Existing records cannot be moved into another project")
    new_rows = ~old_rows
    raw_project = proposed.loc[new_rows, "project_id"]
    if not raw_project.map(lambda x: pd.isna(x) or str(x).strip() == "" or str(x).strip() == project_id).all():
        raise ValueError("New records must belong to the selected project")
    proposed.loc[new_rows, "project_id"] = project_id
    ids = set(core["projects"]["project_id"].astype(str))

    if sheet in WORKFLOW_COLUMNS:
        updated, events = apply_project_register(sheet, workflows[sheet], proposed, project_id, ids)
        # apply_project_register validates IDs, statuses, dates and all required fields.
        changes = dict(workflows)
        changes[sheet] = updated
        return dict(core), changes, events

    remaining = core[sheet].loc[~core[sheet]["project_id"].astype(str).eq(project_id)]
    combined = validated_frame(sheet, pd.concat([remaining, proposed], ignore_index=True))
    changes = dict(core)
    changes[sheet] = combined
    if sheet == "activities" and new_ids:
        # Every activity must have exactly one cost row. A new activity starts
        # with zero actual and committed cost; the ledger is editable afterwards.
        initial_costs = pd.DataFrame([{
            "activity_id": rid, "project_id": project_id,
            "actual_cost": 0.0, "committed_cost": 0.0,
        } for rid in sorted(new_ids)])
        changes["costs"] = validated_frame("costs", pd.concat([
            core["costs"], initial_costs
        ], ignore_index=True))
    # Validate whole project graph and all other projects before applying edits.
    for pid in ids:
        compute(select_project(changes, pid))
    verified = project_sheet(changes, workflows, sheet, project_id)
    events = _change_events(original, verified, key, sheet, project_id)
    if sheet == "activities":
        for rid in sorted(new_ids):
            events.append({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "actor": "demo_session", "project_id": project_id,
                "register": "costs", "record_id": rid,
                "action": "created", "fields": "linked cost row (initialized to zero)",
            })
    return changes, dict(workflows), events


def workbook_bytes(core: dict, workflows: dict, project_id: str) -> bytes:
    """Generate a styled multi-worksheet .xlsx with a safe, formula-free writer."""
    import xlsxwriter
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {
        "in_memory": True, "strings_to_formulas": False, "strings_to_urls": False,
    })
    title = workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#17324F", "valign": "vcenter", "border": 0})
    date_style = workbook.add_format({"num_format": "yyyy-mm-dd"})
    integer = workbook.add_format({"num_format": "#,##0"})
    decimal = workbook.add_format({"num_format": "#,##0.0"})
    intro = workbook.add_worksheet("Guide")
    intro.set_column("A:A", 25)
    intro.set_column("B:B", 96)
    intro.write("A1", "PEIMS WORKBOOK", title)
    intro.write("B1", "Fictional project demonstration — no company connection", title)
    intro.write_row("A3", ["Project", project_id])
    intro.write_row("A4", ["Scope", "Project-scoped records only; changes are not automatically synced to PEIMS."])
    intro.write_row("A5", ["Import", "Upload one selected worksheet through Spreadsheet studio → Excel exchange."])
    intro.write_row("A6", ["Edit", "Keep existing record IDs and project IDs unchanged. Add rows with a new unique ID; PEIMS validates them."])
    intro.write_row("A7", ["Formulas", "Formula cells are rejected on import; calculated project KPIs remain authoritative in PEIMS."])
    intro.write_row("A8", ["Security", "Session-only edits; do not upload Newmont or other confidential information."])
    intro.write_row("A9", ["Note", "Add activities to create linked zero-cost rows automatically. Progress snapshots remain read-only."])
    for row in range(3, 10):
        intro.set_row(row-1, 27)

    for sheet in SHEET_NAMES:
        data = normalize_for_export(project_sheet(core, workflows, sheet, project_id))
        ws = workbook.add_worksheet(sheet)
        ws.freeze_panes(1, 0)
        ws.set_row(0, 26)
        for ci, name in enumerate(data.columns):
            ws.write(0, ci, name, title)
            max_chars = max([len(str(name))] + [len(str(v)) for v in data[name].head(60).tolist()])
            ws.set_column(ci, ci, min(42, max(12, max_chars + 3)))
        for ri, row in enumerate(data.itertuples(index=False, name=None), 1):
            for ci, value in enumerate(row):
                if pd.isna(value):
                    ws.write_blank(ri, ci, None)
                elif isinstance(value, (pd.Timestamp, datetime)):
                    ws.write_datetime(ri, ci, value.to_pydatetime() if hasattr(value, "to_pydatetime") else value, date_style)
                elif isinstance(value, bool):
                    ws.write_boolean(ri, ci, value)
                elif isinstance(value, (int, float)):
                    ws.write_number(ri, ci, float(value), decimal if isinstance(value, float) else integer)
                else:
                    ws.write_string(ri, ci, str(value)[:32000])
        if len(data):
            ws.autofilter(0, 0, len(data), len(data.columns) - 1)
            ws.conditional_format(1, 0, len(data), len(data.columns)-1, {
                "type": "formula", "criteria": "=MOD(ROW(),2)=0",
                "format": workbook.add_format({"bg_color": "#F3F6FA"})
            })
    workbook.close()
    return output.getvalue()


def imported_sheet(payload: bytes, sheet: str) -> pd.DataFrame:
    """Read only the selected workbook sheet; refuse formulas, oversized ZIPs, macros."""
    from openpyxl import load_workbook
    if sheet not in EDITABLE_SHEETS:
        raise ValueError("This worksheet is not editable")
    if not payload or len(payload) > MAX_XLSX_BYTES:
        raise ValueError("Excel workbook must be under 4 MB")
    try:
        with ZipFile(BytesIO(payload)) as z:
            entries = z.infolist()
            if len(entries) > 400 or sum(x.file_size for x in entries) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("Workbook exceeds safety limits")
            if any("vbaProject.bin" in x.filename for x in entries):
                raise ValueError("Macro-enabled workbooks are not allowed")
    except BadZipFile as exc:
        raise ValueError("Invalid Excel workbook") from exc
    try:
        wb = load_workbook(BytesIO(payload), read_only=True, data_only=False, keep_links=False)
        try:
            if sheet not in wb.sheetnames:
                raise ValueError(f"Workbook has no '{sheet}' worksheet")
            ws = wb[sheet]
            if ws.max_row and ws.max_row > MAX_SHEET_ROWS + 1:
                raise ValueError("Worksheet contains too many rows")
            if ws.max_column and ws.max_column > 40:
                raise ValueError("Worksheet contains too many columns")
            rows = list(ws.iter_rows(values_only=False))
            if any(cell.data_type == "f" for row in rows for cell in row):
                raise ValueError("Formula cells cannot be imported into project records")
        finally:
            wb.close()
        imported = pd.read_excel(BytesIO(payload), sheet_name=sheet, engine="openpyxl")
    except (OSError, KeyError) as exc:
        raise ValueError("Could not read selected worksheet") from exc
    if len(imported) > MAX_SHEET_ROWS:
        raise ValueError("Worksheet contains too many records")
    return imported


def safe_csv(frame: pd.DataFrame) -> str:
    """Escape spreadsheet formula injection when a CSV is opened in Excel."""
    copy = normalize_for_export(frame)
    for col in copy.columns:
        if pd.api.types.is_object_dtype(copy[col]):
            copy[col] = copy[col].map(lambda x: "'" + x if isinstance(x, str) and x.startswith(("=", "+", "-", "@", "\t", "\r")) else x)
    return copy.to_csv(index=False)
