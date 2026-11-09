"""PEIMS — Project Engineering Intelligence & Management System (fictional prototype).

Run with: streamlit run app.py
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from workflow import (WORKFLOW_COLUMNS, DATE_COLUMNS, PRIMARY_KEYS, STATUSES,
                      validate_workflow, workflow_metrics, apply_project_register,
                      normalize_for_export, make_snapshot, read_snapshot, workflow_report_appendix)

from project_controls import critical_path, cost_forecast

from analytics import (
    DATASET_COLUMNS,
    compute,
    make_alerts,
    money,
    select_project,
    validated_frame,
    weekly_report,
)

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"

st.set_page_config(
    page_title="PEIMS | Project Engineering Intelligence",
    page_icon="⚒️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1480px; }
    #MainMenu {visibility: hidden;}
    h1,h2,h3 { letter-spacing: -.035em; }
    h1 { font-size: 2.1rem!important; }
    [data-testid="stMetric"] { background: #14253b; border: 1px solid #2b4056;
        border-radius: 13px; padding: 15px 17px; }
    [data-testid="stMetricLabel"] {color:#b5c6d5;}
    [data-testid="stMetricValue"] {color:#ffffff;}
    [data-testid="stSidebar"] {background: #101b2b;}
    [data-testid="stAppViewContainer"] {background: #0b1625;}
    [data-testid="stHeader"] {background: #0b1625;}
    .kicker {font-size: .72rem; letter-spacing:.15em; font-weight: 800; color:#e9b65f; }
    .subtitle {color:#b2bfd0; font-size: .94rem; }
    .sectionline { border-bottom:1px solid #304156; margin: 10px 0 16px; }
    .peims-note {background:#15283e; border-left: 3px solid #d6a251; border-radius: 7px;
        padding: .85rem 1.1rem; color:#dbe5ef; margin-bottom:1rem;}
    .rule-card {padding:13px 15px; border-radius:10px; margin-bottom: 9px;
        background:#14253b; border: 1px solid #304056;}
    .rule-card strong {color:#f0c278;}
    .rule-card small {color:#a9bbce;}
    [data-testid="stTabs"] button {font-size: .89rem;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def get_demo_data() -> dict[str, pd.DataFrame]:
    return {name: validated_frame(name, pd.read_csv(DATA_DIR / f"{name}.csv")) for name in DATASET_COLUMNS}


@st.cache_data(show_spinner=False)
def get_sample_dependencies() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "dependencies.csv")


@st.cache_data(show_spinner=False)
def get_demo_workflows() -> dict[str, pd.DataFrame]:
    project_ids = set(get_demo_data()["projects"]["project_id"].astype(str))
    return {name: validate_workflow(name, pd.read_csv(DATA_DIR / f"{name}.csv"), project_ids)
            for name in WORKFLOW_COLUMNS}


def log_session_change(register: str, record_id: str, action: str, project_id: str):
    events = list(st.session_state.get("change_history", []))
    events.append({"timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "actor": "demo_session", "project_id": project_id,
                   "register": register, "record_id": record_id, "action": action})
    st.session_state["change_history"] = events[-250:]


def chart_style(fig, height: int = 340):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dce7f1", size=12), margin=dict(t=18, b=28, l=22, r=18),
        legend=dict(orientation="h", y=1.13, x=0),
        xaxis=dict(gridcolor="rgba(150,165,190,.16)", zerolinecolor="#556478"),
        yaxis=dict(gridcolor="rgba(150,165,190,.16)", zerolinecolor="#556478"),
    )
    return fig


def df_display(df: pd.DataFrame, columns: dict[str, str]):
    return df.loc[:, list(columns)].rename(columns=columns).reset_index(drop=True)


def flags_panel(alerts: list[dict]):
    if not alerts:
        st.success("No flags for the current dataset.")
    for a in alerts:
        heading = escape(f"{a['severity']}  /  {a['area']}")
        msg = escape(a["message"])
        nxt = escape(a["next"])
        st.markdown(
            f'<div class="rule-card"><strong>{heading}</strong><div>{msg}</div>'
            f'<small>Suggested follow-up: {nxt}</small></div>', unsafe_allow_html=True,
        )


def show_overview(result: dict):
    k, info = result["kpi"], result["info"]
    a, b, c, d = st.columns(4)
    a.metric("Physical completion", f"{k['actual_pct']:.1f}%", f"{k['progress_gap']:+.1f} pp vs baseline", delta_color="normal")
    b.metric("Baseline target", f"{k['planned_pct']:.1f}%", "Linear baseline")
    c.metric("Recorded expenditure", money(k["actual_cost"], info["currency"]))
    d.metric("Open high risks", k["open_high_risks"])
    left, right = st.columns([1.6, 1], gap="large")
    with left:
        st.subheader("Progress trend")
        hist = result["history"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist["week_ending"], y=hist["planned_pct"],
                                 mode="lines+markers", name="Planned", line=dict(color="#dcb16b", width=3)))
        fig.add_trace(go.Scatter(x=hist["week_ending"], y=hist["actual_pct"],
                                 mode="lines+markers", name="Actual", line=dict(color="#39bfb0", width=3),
                                 fill="tonexty", fillcolor="rgba(57,191,176,.10)"))
        fig.update_yaxes(range=[0, 100], title="% complete")
        fig.update_xaxes(title="Week ending")
        st.plotly_chart(chart_style(fig, 385), use_container_width=True)
        st.caption("Trend points are fictional weekly records. Current KPIs are recalculated from the activity register.")
    with right:
        st.subheader("Management attention")
        st.metric("Late activities", k["late_activities"])
        st.metric("Overdue purchase orders", k["overdue_po"])
        st.metric("Overdue action items", k["overdue_actions"])
        st.caption("Flags are threshold-based. They do not replace site verification or safety controls.")
    st.subheader("Prioritized follow-ups")
    flags_panel(make_alerts(result)[:4])


def show_schedule(result: dict):
    acts, k = result["activities"], result["kpi"]
    a, b, c = st.columns(3)
    a.metric("Activities", len(acts))
    b.metric("Behind baseline >10 pp", k["slipping_activities"])
    c.metric("Schedule performance index", f"{k['spi']:.2f}" if k["spi"] is not None else "N/A")
    st.subheader("Progress by activity")
    df = acts.sort_values("wbs", ascending=False)
    fig = go.Figure()
    for label, field, color in [("Baseline", "planned_pct", "#e2b66f"), ("Actual", "actual_pct", "#3fc2b4")]:
        fig.add_trace(go.Bar(y=df["activity"], x=df[field], name=label, orientation="h", marker_color=color))
    fig.update_layout(barmode="group", height=max(420, len(df) * 48), xaxis_title="Completion (%)", xaxis_range=[0, 105])
    st.plotly_chart(chart_style(fig, max(420, len(df) * 48)), use_container_width=True)
    st.subheader("Baseline activity timeline")
    timeline = acts.sort_values("start_date")
    fig2 = px.timeline(timeline, x_start="start_date", x_end="finish_date", y="activity",
                       color="owner", hover_data={"actual_pct":True, "wbs":True})
    fig2.update_yaxes(autorange="reversed")
    fig2.add_vline(x=result["date"].timestamp() * 1000, line_dash="dash", line_color="#e2b66f")
    st.plotly_chart(chart_style(fig2, max(420, len(acts) * 45)), use_container_width=True)
    st.caption("Original baseline dates. A dependency-aware CPM illustration is shown below, not a P6 replacement.")
    st.subheader("Dependency network & critical path · limited CPM")
    try:
        pid = str(result["info"]["project_id"])
        links = get_sample_dependencies()
        links = links.loc[links["project_id"].eq(pid)].copy()
        cpm = critical_path(acts, links)
        c1, c2, c3 = st.columns(3)
        c1.metric("Dependency-modeled finish", cpm["model_finish"])
        c2.metric("Critical activities", len(cpm["critical_activity_ids"]))
        c3.metric("Links (FS only)", len(links))
        network = pd.DataFrame(cpm["activities"])
        network = network.merge(acts[["activity_id", "activity"]], on="activity_id", how="left")
        st.dataframe(network[["activity_id", "activity", "earliest_start", "earliest_finish", "total_float_days", "critical"]],
                     use_container_width=True, hide_index=True)
        st.download_button("Download limited CPM table", network.to_csv(index=False),
                           file_name=f"PEIMS_CPM_{pid}.csv", mime="text/csv")
        st.caption(cpm["assumptions"] + " Criticality is based on the modeled network, not field progress or an approved P6 baseline.")
    except (ValueError, KeyError, TypeError) as ex:
        st.warning(f"Dependency network could not be calculated for current session data: {ex}")

    with st.expander("Edit activity completion (this browser session)", expanded=False):
        st.caption("You can change actual completion %. Baseline dates and budgets remain fixed in this editor.")
        base_acts = st.session_state.get("current_core", {}).get("activities")
        if base_acts is not None:
            chosen_pid = str(result["info"]["project_id"])
            subset = base_acts.loc[base_acts["project_id"].eq(chosen_pid), ["activity_id", "activity", "actual_pct"]].copy()
            with st.form(f"activity_progress_{chosen_pid}"):
                changes = st.data_editor(subset, hide_index=True, disabled=["activity_id", "activity"],
                                         key=f"activity_editor_{chosen_pid}", use_container_width=True)
                submitted = st.form_submit_button("Save activity progress in this session")
            if submitted:
                try:
                    updates = changes.set_index("activity_id")["actual_pct"]
                    if set(updates.index) != set(subset["activity_id"]):
                        raise ValueError("Activity IDs cannot be changed")
                    candidate = base_acts.copy()
                    changed_ids = []
                    for idx in candidate.index[candidate["project_id"].eq(chosen_pid)]:
                        aid = candidate.at[idx, "activity_id"]
                        new_value = float(updates[aid])
                        if float(candidate.at[idx, "actual_pct"]) != new_value:
                            changed_ids.append(aid)
                            candidate.at[idx, "actual_pct"] = new_value
                    candidate = validated_frame("activities", candidate)
                    records = dict(st.session_state["current_core"])
                    records["activities"] = candidate
                    compute(select_project(records, chosen_pid))
                    overrides = dict(st.session_state.get("overrides", {}))
                    overrides["activities"] = candidate
                    st.session_state["overrides"] = overrides
                    for aid in changed_ids:
                        log_session_change("activities", str(aid), "progress updated", chosen_pid)
                    st.success(f"Saved {len(changed_ids)} activity changes to this session")
                    st.rerun()
                except (ValueError, KeyError, TypeError) as exc:
                    st.error(f"Progress changes rejected: {exc}")
    st.subheader("Activity register")
    show = acts.sort_values("wbs").copy()
    show["start_date"] = show["start_date"].dt.strftime("%Y-%m-%d")
    show["finish_date"] = show["finish_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(df_display(show, {"wbs":"WBS", "activity":"Activity", "owner":"Owner", "start_date":"Start", "finish_date":"Finish", "planned_pct":"Planned %", "actual_pct":"Actual %", "variance_pp":"Variance (pp)", "is_late":"Past finish"}),
                 use_container_width=True, hide_index=True)
    st.download_button("Download activity controls CSV", acts.to_csv(index=False), "activity_controls.csv", "text/csv")


def show_financials(result: dict):
    k, currency, acts = result["kpi"], result["info"]["currency"], result["activities"]
    cols = st.columns(4)
    cols[0].metric("Budget at completion", money(k["budget"], currency))
    cols[1].metric("Actual cost (AC)", money(k["actual_cost"], currency))
    cols[2].metric("Earned value (EV)", money(k["earned_value"], currency))
    cols[3].metric("CPI", f"{k['cpi']:.2f}" if k["cpi"] is not None else "N/A")
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        st.subheader("Earned value comparison")
        fig = go.Figure(go.Bar(
            x=["Planned value (PV)", "Earned value (EV)", "Actual cost (AC)"],
            y=[k["planned_value"], k["earned_value"], k["actual_cost"]],
            marker_color=["#e0b76d", "#39bfae", "#87a9d4"],
            text=[money(v, currency) for v in [k["planned_value"], k["earned_value"], k["actual_cost"]]],
            textposition="outside"))
        fig.update_yaxes(title=f"{currency}")
        st.plotly_chart(chart_style(fig, 365), use_container_width=True)
    with right:
        st.subheader("Cost signals")
        st.metric("Cost variance: EV − AC", money(k["cost_variance"], currency))
        st.metric("Schedule variance: EV − PV", money(k["schedule_variance_value"], currency))
        st.metric("Committed, not yet actual", money(k["committed_cost"], currency))
        st.caption("Commitments are shown separately and are not added to recorded actual expenditure. Confirm their accounting treatment with project controls.")
    st.subheader("Estimate at completion · CPI continuation scenario")
    try:
        fc = cost_forecast(k["budget"], k["earned_value"], k["actual_cost"], k["committed_cost"])
        a, b, c = st.columns(3)
        a.metric("EAC (CPI scenario)", money(fc["eac_cpi"], currency) if fc["eac_cpi"] is not None else "N/A")
        b.metric("Estimate to complete", money(fc["etc_cpi"], currency) if fc["etc_cpi"] is not None else "N/A")
        c.metric("Variance at completion", money(fc["vac_cpi"], currency) if fc["vac_cpi"] is not None else "N/A")
        st.caption(fc["method"] + " Commitments are disclosed separately, not double-counted. Forecasts need approved progress measurement and accounting review.")
    except ValueError as ex:
        st.warning(f"Cost forecast not available: {ex}")
    st.subheader("Cost by work package")
    df = acts.sort_values("baseline_budget", ascending=False)
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=df["activity"], y=df["baseline_budget"], name="Baseline budget", marker_color="#e0b76d"))
    fig2.add_trace(go.Bar(x=df["activity"], y=df["actual_cost"], name="Actual costs", marker_color="#39bfae"))
    fig2.update_layout(barmode="group", xaxis_tickangle=-32)
    st.plotly_chart(chart_style(fig2, 445), use_container_width=True)
    with st.expander("Definitions and limitations", expanded=False):
        st.markdown("**EV** = budget × recorded physical completion. **PV** = budget × assumed planned completion. **AC** = recorded expenditure. **CPI** = EV/AC. **SPI** = EV/PV. The baseline assumes linear activity progression; real project baselines and progress measurement must be approved and verified.")


def show_procurement(result: dict):
    p = result["procurement"].copy()
    a, b, c = st.columns(3)
    a.metric("Open purchase orders", int((~p["received"]).sum()))
    b.metric("Overdue orders", int(p["overdue"].sum()))
    c.metric("Critical deliveries overdue", result["kpi"]["critical_overdue_po"])
    st.subheader("Delivery exceptions")
    late = p.loc[p["overdue"]].sort_values("days_late", ascending=False)
    if late.empty:
        st.success("No overdue delivery dates in the selected project.")
    else:
        for _, order in late.iterrows():
            st.warning(f"{order['po_id']} — {order['item']}: {int(order['days_late'])} day(s) overdue. Critical: {order['critical']}. Follow up with {order['supplier']}.")
    st.subheader("Procurement register")
    p["expected_date"] = p["expected_date"].dt.strftime("%Y-%m-%d")
    p["received_date"] = p["received_date"].dt.strftime("%Y-%m-%d").fillna("—")
    st.dataframe(df_display(p, {"po_id":"PO", "item":"Item", "supplier":"Supplier", "status":"Status", "expected_date":"Expected", "received_date":"Received", "po_value":"PO value", "critical":"Critical", "days_late":"Days late"}),
                 use_container_width=True, hide_index=True)


def show_risks(result: dict):
    risks, actions = result["risks"], result["actions"]
    a,b,c = st.columns(3)
    a.metric("Open risks", int(risks["open"].sum()))
    b.metric("High risks", result["kpi"]["open_high_risks"])
    c.metric("Overdue actions", result["kpi"]["overdue_actions"])
    left, right = st.columns([.82, 1.18], gap="large")
    with left:
        st.subheader("Risk matrix")
        open_risks = risks.loc[risks["open"]]
        matrix = pd.crosstab(open_risks["impact"], open_risks["probability"]).reindex(index=range(1,6),columns=range(1,6),fill_value=0)
        fig = go.Figure(go.Heatmap(z=matrix.values, x=[1,2,3,4,5], y=[1,2,3,4,5],
                                   text=matrix.values, texttemplate="%{text}", zmin=0,
                                   colorscale=[[0,"#25384c"],[.5,"#bd9545"],[1,"#c85b57"]], showscale=False))
        fig.update_xaxes(title="Probability (1–5)")
        fig.update_yaxes(title="Impact (1–5)")
        st.plotly_chart(chart_style(fig, 365), use_container_width=True)
        st.caption("Demonstration qualitative 5×5 matrix. Site risk assessment procedures take precedence.")
    with right:
        st.subheader("Priority action register")
        acts = actions.copy().sort_values(["overdue", "due_date"],ascending=[False,True])
        acts["due_date"] = acts["due_date"].dt.strftime("%Y-%m-%d")
        st.dataframe(df_display(acts, {"action_id":"ID", "action":"Action", "owner":"Owner", "due_date":"Due", "priority":"Priority", "status":"Status", "overdue":"Overdue"}), use_container_width=True, hide_index=True, height=355)
    st.subheader("Risk register")
    st.dataframe(df_display(risks.sort_values("score",ascending=False), {"risk_id":"ID", "risk":"Risk", "category":"Area", "probability":"P", "impact":"I", "score":"Score", "level":"Level", "status":"Status", "owner":"Owner", "mitigation":"Mitigation"}), use_container_width=True, hide_index=True)


def show_reports(result: dict, workflows: dict[str, pd.DataFrame] | None = None):
    st.subheader("Draft weekly engineering report")
    st.markdown('<div class="peims-note">This is an automatically assembled <b>rule-based report</b> for review. It is not an approved engineering document or a generative AI output.</div>', unsafe_allow_html=True)
    md = weekly_report(result)
    if workflows is not None:
        md += workflow_report_appendix(workflows, result["info"]["project_id"], result["date"])
    left, right = st.columns([.65, .35])
    with left:
        st.download_button("Download Markdown report", md, file_name=f"PEIMS_weekly_report_{result['info']['project_id']}.md", mime="text/markdown", use_container_width=True)
    with right:
        st.download_button("Download text report", md, file_name=f"PEIMS_weekly_report_{result['info']['project_id']}.txt", mime="text/plain", use_container_width=True)
    with st.container(border=True):
        st.markdown(md)


def show_register_editor(name: str, workflows: dict[str, pd.DataFrame], project_id: str,
                         valid_projects: set[str], snapshot_date):
    """Session-scoped add/edit/remove table, with per-record change history."""
    full = workflows[name]
    shown = full.loc[full["project_id"].eq(project_id)].copy()
    k = PRIMARY_KEYS[name]
    with st.expander("Edit records / add rows / remove rows (session only)", expanded=False):
        st.caption("Use the '+' row at the bottom to create a record. Unique IDs are required. "
                   "All edits are private to this browser session and not written to the cloud database.")
        fields = [x for x in WORKFLOW_COLUMNS[name] if x != "project_id"]
        editable = normalize_for_export(shown[fields])
        with st.form(f"edit_{name}_{project_id}"):
            revised = st.data_editor(editable, hide_index=True, num_rows="dynamic",
                                     use_container_width=True, key=f"table_{name}_{project_id}")
            accepted = st.form_submit_button(f"Apply {name} changes")
        if accepted:
            try:
                updated, events = apply_project_register(name, full, revised, project_id, valid_projects)
                overrides = dict(st.session_state.get("workflow_overrides", {}))
                overrides[name] = updated
                st.session_state["workflow_overrides"] = overrides
                audit = list(st.session_state.get("change_history", []))
                st.session_state["change_history"] = (audit + events)[-250:]
                st.success(f"Saved {len(events)} changes to this browser session")
                st.rerun()
            except (ValueError, KeyError, TypeError) as exc:
                st.error(f"Changes rejected: {exc}")
    if name == "contractors":
        cols = ["contractor_id", "company", "scope", "lead", "status", "planned_finish", "progress_pct", "notes"]
    elif name == "rfis":
        cols = ["rfi_id", "subject", "discipline", "assigned_to", "due_date", "status", "critical", "response_summary"]
    else:
        cols = ["document_id", "title", "discipline", "revision", "status", "owner", "updated_on", "reference"]
    st.dataframe(normalize_for_export(shown[cols]), hide_index=True, use_container_width=True)
    st.download_button(f"Download {name} CSV", normalize_for_export(shown).to_csv(index=False),
                       file_name=f"{project_id}_{name}.csv", mime="text/csv", key=f"dl_{name}_{project_id}")


def show_workflow_hub(core: dict[str, pd.DataFrame], workflows: dict[str, pd.DataFrame],
                      project_id: str, snapshot_date):
    st.subheader("Engineering workflow centre")
    st.markdown('<div class="peims-note"><b>SANDBOX EDITING</b> · Data changes are visible only in your current session. '
                'They are not shared, durable or approved for confidential mine records. '
                'Use the workspace backup to save fictional changes.</div>', unsafe_allow_html=True)
    valid_projects = set(core["projects"]["project_id"].astype(str))
    m = workflow_metrics(workflows, project_id, snapshot_date)
    a,b,c,d = st.columns(4)
    a.metric("Active / listed contractors", m["contractors"])
    b.metric("At-risk contractors", m["at_risk_contractors"])
    c.metric("Open RFIs", m["pending_rfis"])
    d.metric("Pending document reviews", m["pending_documents"])
    contractors, rfis, docs, workspace = st.tabs(["Contractors", "RFIs", "Document register", "Workspace & history"])
    with contractors:
        st.subheader("Contractor performance")
        st.metric("Late contractor finish dates", m["overdue_contractors"])
        st.caption("Progress and status are manually entered. This is not connected to contracts, procurement or payroll systems.")
        show_register_editor("contractors", workflows, project_id, valid_projects, snapshot_date)
    with rfis:
        st.subheader("Requests for information")
        a,b = st.columns(2)
        a.metric("Overdue open RFIs", m["overdue_rfis"])
        b.metric("Critical open RFIs", m["critical_open_rfis"])
        st.caption("'Open' and 'In Review' are counted as outstanding; status updates are not approvals.")
        show_register_editor("rfis", workflows, project_id, valid_projects, snapshot_date)
    with docs:
        st.subheader("Engineering document metadata")
        st.caption("Tracks titles, owners, revisions and review status only. Files are not uploaded or stored.")
        show_register_editor("documents", workflows, project_id, valid_projects, snapshot_date)
    with workspace:
        st.subheader("Save or restore your demonstration workspace")
        st.warning("No authenticated multiuser database exists in this version. "
                   "A download is necessary if you want to retain demo edits after your browser session ends.")
        history = st.session_state.get("change_history", [])
        payload = make_snapshot(core, workflows, history, list(DATASET_COLUMNS))
        st.download_button("Download complete PEIMS workspace (.zip)", payload,
                           file_name=f"PEIMS_v03_workspace_{project_id}.zip", mime="application/zip",
                           key="snapshot_dl", use_container_width=True)
        backup = st.file_uploader("Restore a PEIMS v0.3 workspace ZIP", type="zip", key="restore_snapshot")
        if st.button("Validate and restore snapshot", disabled=backup is None, key="restore_button"):
            try:
                if backup.size > 8 * 1024 * 1024:
                    raise ValueError("Backup must be smaller than 8 MB")
                refreshed_core, refreshed_workflows, restored_history = read_snapshot(
                    backup.getvalue(), list(DATASET_COLUMNS), validated_frame, compute, select_project)
                st.session_state["overrides"] = refreshed_core
                st.session_state["workflow_overrides"] = refreshed_workflows
                st.session_state["change_history"] = restored_history[-249:]
                log_session_change("workspace", "full_snapshot", "restored", project_id)
                st.success("Validated snapshot loaded into this session")
                st.rerun()
            except (ValueError, TypeError, KeyError) as exc:
                st.error(f"Could not restore workspace: {exc}")
        st.subheader("Session change history")
        if history:
            st.dataframe(pd.DataFrame(history).iloc[::-1], hide_index=True, use_container_width=True)
            st.download_button("Download history CSV", pd.DataFrame(history).to_csv(index=False),
                               "PEIMS_session_history.csv", mime="text/csv")
        else:
            st.info("No changes in this browser session yet.")
        if st.button("Reset demo workspace to initial records", key="all_reset"):
            st.session_state["overrides"] = {}
            st.session_state["workflow_overrides"] = {}
            st.session_state["change_history"] = []
            st.rerun()
        st.caption("This is a session change history, NOT a tamper-resistant compliance audit trail.")


def show_data_controls(base_data: dict[str, pd.DataFrame]):
    st.subheader("Data exchange — CSV")
    st.markdown("Download the included example CSVs, replace them with **non-sensitive, authorized** data, and upload one dataset at a time. Imported files affect only this app session and are **not saved** in a database.")
    st.warning("Do not upload Newmont internal engineering files, employee data, contracts, mine plans, or security-sensitive information to a public prototype or unapproved cloud service.")
    selected = st.selectbox("Dataset", options=list(DATASET_COLUMNS), format_func=lambda v: v.replace('_',' ').title())
    st.caption("Expected fields: " + ", ".join(DATASET_COLUMNS[selected]))
    st.download_button(f"Download {selected}.csv sample", base_data[selected].to_csv(index=False), file_name=f"{selected}_example.csv", mime="text/csv")
    uploaded = st.file_uploader(f"Import replacement {selected}.csv", type=["csv"], key=f"upload_{selected}")
    if uploaded is not None and st.button("Validate and apply to this session", type="primary"):
        try:
            incoming = validated_frame(selected, pd.read_csv(uploaded))
            overrides = dict(st.session_state.get("overrides", {}))
            overrides[selected] = incoming
            candidate = {name: overrides.get(name, base_data[name]) for name in DATASET_COLUMNS}
            for project_id in candidate["projects"]["project_id"]:
                compute(select_project(candidate, project_id))
            st.session_state["overrides"] = overrides
            log_session_change(selected, "imported_csv", "imported", "all_projects")
            st.success(f"Validated and applied {selected}. Refresh or reset to return to the sample dataset.")
            st.rerun()
        except Exception as exc:
            st.error(f"Import rejected: {exc}")
    if st.button("Reset ALL imported files to demo data"):
        st.session_state["overrides"] = {}
        st.rerun()
    st.subheader("Current example data")
    st.dataframe(base_data[selected].head(12), use_container_width=True, hide_index=True)
    st.caption("You can also edit CSV files in the project data/ folder and restart the app; the app cache can be cleared from the Streamlit menu.")


def main():
    base_data = get_demo_data()
    all_data = {name: st.session_state.get("overrides", {}).get(name, base_data[name]) for name in DATASET_COLUMNS}
    base_workflows = get_demo_workflows()
    workflows = {name: st.session_state.get("workflow_overrides", {}).get(name, base_workflows[name])
                 for name in WORKFLOW_COLUMNS}
    st.session_state["current_core"] = all_data
    st.sidebar.markdown('<div class="kicker">⚒  PEIMS / CONTROLS 0.5</div>', unsafe_allow_html=True)
    st.sidebar.title("Project controls")
    st.sidebar.caption("Fictional data • No Newmont integration")
    ps = all_data["projects"]
    chosen = st.sidebar.selectbox("Active project", ps["project_id"].tolist(), format_func=lambda p: ps.loc[ps["project_id"].eq(p), "project_name"].iloc[0])
    st.sidebar.divider()
    st.sidebar.markdown("**Data status**")
    st.sidebar.caption("Session workspace: changes must be backed up manually")
    st.sidebar.caption("Enterprise API: separate, not connected to this public demo")
    st.sidebar.markdown("**Reporting date**")
    chosen_info = ps.loc[ps["project_id"].eq(chosen)].iloc[0]
    st.sidebar.caption(pd.Timestamp(chosen_info["snapshot_date"]).strftime("%d %B %Y"))
    st.sidebar.divider()
    st.sidebar.info("Use this project for learning, demonstration and portfolio purposes—not real mining decisions.")
    st.markdown('<div class="kicker">PROJECT ENGINEERING INTELLIGENCE & MANAGEMENT SYSTEM</div>', unsafe_allow_html=True)
    st.title(escape(chosen_info["project_name"]))
    st.markdown(f'<p class="subtitle">{escape(chosen_info["type"])}  ·  {escape(chosen_info["location"])}  ·  Reporting snapshot: {pd.Timestamp(chosen_info["snapshot_date"]):%d %b %Y}</p>', unsafe_allow_html=True)
    st.markdown('<div class="peims-note"><b>DEMONSTRATION ONLY</b> · All budgets, activity records, equipment descriptions, and risk scores are synthetic. This is an independent portfolio prototype, not a Newmont product.</div>', unsafe_allow_html=True)
    try:
        result = compute(select_project(all_data, chosen))
    except Exception as exc:
        st.error(f"The uploaded dataset has inconsistent records: {exc}. Reset your inputs under Data Studio.")
        # Data tab stays reachable for recovery via the reset interface.
        show_data_controls(base_data)
        return
    tabs = st.tabs(["◈ Command centre", "▤ Schedule", "◉ Cost control", "▣ Procurement", "⚑ Risks & actions", "▧ Reports", "⚙ Data studio", "▦ Workflows"])
    with tabs[0]: show_overview(result)
    with tabs[1]: show_schedule(result)
    with tabs[2]: show_financials(result)
    with tabs[3]: show_procurement(result)
    with tabs[4]: show_risks(result)
    with tabs[5]: show_reports(result, workflows)
    with tabs[6]: show_data_controls(base_data)
    with tabs[7]: show_workflow_hub(all_data, workflows, chosen, chosen_info["snapshot_date"])
    st.divider()
    st.caption("PEIMS prototype 0.5 | Public demo remains session-only. The v0.5 persistent multiuser API is source code only and is not connected to this dashboard. No company integration or authorization. Human engineering verification is essential.")


if __name__ == "__main__":
    main()
