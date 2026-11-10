"""PEIMS — Project Engineering Intelligence & Management System (fictional UI v0.5.4).

Run with: streamlit run app.py
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from datetime import datetime, timezone
from importlib import reload

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from workflow import (WORKFLOW_COLUMNS, DATE_COLUMNS, PRIMARY_KEYS, STATUSES,
                      validate_workflow, workflow_metrics, apply_project_register,
                      normalize_for_export, make_snapshot, read_snapshot, workflow_report_appendix)

from project_controls import critical_path, cost_forecast
from sheet_engine import (SHEET_NAMES, EDITABLE_SHEETS, SHEET_LABELS, SHEET_KEYS,
                          project_sheet, apply_sheet, workbook_bytes, imported_sheet, safe_csv)
from smart_entry import suggestions, new_record_id, SUGGESTED_FIELDS, validate_smart_inputs
from bi_engine import SOURCE_SPECS, source_frame, build_analysis
from gantt import gantt_figure, gantt_rows
from pm_ui import show_work_management, initialize_work_items
from work_items import task_metrics
from experience import HOME_CHOICES, home_choice_counts, priority_actions, activity_status, render_welcome

# Streamlit Cloud can hot-reload app.py while retaining a previous imported ui_shell.
# Refresh the tiny, pure presentation module before binding its navigation list.
# Otherwise the new Home and Documents callbacks can fail against stale choices.
import ui_shell as _ui_shell
reload(_ui_shell)
from ui_shell import (NAVIGATION, NAV_LABELS, attention_flags, render_css,
                      render_brand, render_header, render_intro, render_safety, render_footer)
from visuals import (progress_s_curve, schedule_variance, dependency_timeline,
                     cost_variance_waterfall, cost_exposure_quadrant,
                     procurement_delivery_map, risk_severity_matrix, insight_summary)

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
    initial_sidebar_state="auto",
)




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
        font=dict(size=12), margin=dict(t=18, b=28, l=22, r=18),
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
            f'<div class="peims-alert"><strong>{heading}</strong><div>{msg}</div>'
            f'<small>Suggested follow-up: {nxt}</small></div>', unsafe_allow_html=True,
        )


NAV_SCHEMA_VERSION = "studio-v0.6"


def migrate_navigation_session() -> None:
    """Show Home once after upgrading earlier browser sessions.

    Never overwrite normal navigation again after the migration marker is set.
    This also safely recovers a removed or renamed workspace.
    """
    if st.session_state.get("_peims_nav_schema") != NAV_SCHEMA_VERSION:
        st.session_state["workspace_navigation"] = "Home"
        st.session_state["_peims_nav_schema"] = NAV_SCHEMA_VERSION
    elif st.session_state.get("workspace_navigation", "Home") not in NAVIGATION:
        st.session_state["workspace_navigation"] = "Home"


def change_workspace(target: str) -> None:
    """Navigate through the sidebar radio, recovering safely from stale choices."""
    if target not in NAVIGATION:
        st.session_state["workspace_navigation"] = "Home"
        st.session_state["peims_nav_recovered"] = True
        return
    st.session_state["workspace_navigation"] = target


def show_shortcuts(result: dict) -> None:
    """Mobile-friendly, native controls; all shortcuts work from the overview."""
    k = result["kpi"]
    shortcuts = (
        ("Schedule", f"Schedule · {int(k['slipping_activities'])} slipping"),
        ("Cost control", "Cost & forecast"),
        ("Procurement", f"Procurement · {int(k['overdue_po'])} overdue"),
        ("Reports", "Reports & exports"),
    )
    with st.container(key="peims_shortcuts"):
        st.markdown('<div class="peims-shortcut-caption">QUICK ACCESS</div>', unsafe_allow_html=True)
        cols = st.columns(4, gap="small")
        for col, (target, label) in zip(cols, shortcuts):
            with col:
                st.button(label, key=f"peims_go_{target.replace(' ', '_').lower()}",
                          on_click=change_workspace, args=(target,), use_container_width=True,
                          help=f"Open {target} workspace")



def open_gantt_workspace() -> None:
    """Open the dedicated Gantt, not the old activity-list default."""
    st.session_state.pop('peims_activity_detail', None)
    st.session_state['schedule_mode'] = 'Gantt'
    change_workspace('Schedule')


def open_activity_record(activity_id: str) -> None:
    st.session_state["peims_activity_detail"] = activity_id
    st.session_state["schedule_mode"] = "Activities"
    change_workspace("Schedule")


def open_action_record(action_id: str) -> None:
    st.session_state["peims_action_detail"] = action_id
    st.session_state["issues_mode"] = "Actions"
    change_workspace("Risks & actions")


def open_document_record(document_id: str) -> None:
    st.session_state["peims_document_detail"] = document_id
    change_workspace("Documents")


def show_home(result: dict, project: dict, workflows: dict) -> None:
    """A true start page: choose a job first, open analysis only on demand."""
    st.markdown(render_welcome(project, result["kpi"]), unsafe_allow_html=True)
    st.markdown('### Project timeline · at a glance')
    st.caption('Baseline activity windows with the reported completion fraction filled in. '
               'The dashed line marks the project reporting snapshot; this is not an actual-date or forecast Gantt.')
    st.plotly_chart(gantt_figure(result['activities'], result['date'], compact=True, limit=6),
                    use_container_width=True, key='home_project_gantt',
                    config={'displayModeBar': False, 'displaylogo': False})
    st.button('Open full Gantt & schedule →', key='home_full_gantt',
              on_click=open_gantt_workspace, use_container_width=True)
    st.markdown('<div class="peims-home-label">What would you like to do?</div>'
                '<p class="peims-home-sub">Choose one workspace. Detailed analysis is there when you need it.</p>',
                unsafe_allow_html=True)
    counts = home_choice_counts(result, workflows)
    for start in range(0, len(HOME_CHOICES), 2):
        cols = st.columns(2, gap="medium")
        for col, choice in zip(cols, HOME_CHOICES[start:start + 2]):
            with col:
                with st.container(border=True, key=f"home_card_{choice.target.lower().replace(' ', '_').replace('&', 'and')}"):
                    st.markdown(f'<div class="peims-card-icon" aria-hidden="true">{escape(choice.icon)}</div>',
                                unsafe_allow_html=True)
                    st.button(f"{choice.label}  →", key=f"home_open_{choice.target.lower().replace(' ', '_').replace('&', 'and')}",
                              on_click=open_gantt_workspace if choice.target == 'Schedule' else change_workspace,
                              args=() if choice.target == 'Schedule' else (choice.target,),
                              use_container_width=True,
                              help=f"Open the {choice.label.lower()} workspace")
                    st.markdown(f'<div class="peims-card-info">{escape(choice.summary)}</div>'
                                f'<div class="peims-card-count">{escape(counts[choice.target])}</div>',
                                unsafe_allow_html=True)
    st.divider()
    st.markdown('### A few things need attention')
    st.caption('Open an action to inspect the owner, due date and status. All records are fictional.')
    actions = priority_actions(result)
    if actions.empty:
        st.success('No outstanding actions in this project snapshot.')
    else:
        for _, row in actions.iterrows():
            due = pd.Timestamp(row["due_date"]).strftime('%d %b %Y')
            label = f'{row["action"]} · {row["owner"]} · Due {due}'
            st.button(label, key=f'home_action_{row["action_id"]}',
                      on_click=open_action_record, args=(str(row["action_id"]),),
                      use_container_width=True, help='Open action details')
    a, b = st.columns([2, 1])
    with a:
        st.caption('Demonstration workspace · Session-only edits · No live company records')
    with b:
        st.button('View full project analysis →', key='home_open_command_centre',
                  on_click=change_workspace, args=('Command centre',), use_container_width=True)


def show_activity_details(result: dict, row: pd.Series) -> None:
    if st.button('← All activities', key='return_activity_list'):
        st.session_state.pop('peims_activity_detail', None)
        st.rerun()
    st.caption(f'ACTIVITY · {row["activity_id"]} · WBS {row["wbs"]}')
    st.markdown(f'### {row["activity"]}')
    st.info(f'**{activity_status(row)}** · Responsible: {row["owner"]}')
    c1, c2, c3 = st.columns(3)
    c1.metric('Actual completion', f'{float(row["actual_pct"]):.1f}%')
    c2.metric('Planned completion', f'{float(row["planned_pct"]):.1f}%')
    c3.metric('Progress gap', f'{float(row["variance_pp"]):+.1f} pp')
    with st.container(border=True):
        st.write('**Baseline period**')
        st.write(f'{pd.Timestamp(row["start_date"]):%d %b %Y} — {pd.Timestamp(row["finish_date"]):%d %b %Y}')
        st.write(f'**Work package budget:** {money(row["baseline_budget"], result["info"]["currency"])}')
        st.write(f'**Recorded expenditure:** {money(row["actual_cost"], result["info"]["currency"])}')
    with st.expander('Update physical completion · demonstration only', expanded=False):
        st.caption('Edits apply only to this browser session. They do not change an approved schedule.')
        pid = str(result['info']['project_id'])
        activity_id = str(row['activity_id'])
        with st.form(f'activity_detail_edit_{pid}_{activity_id}'):
            new_pct = st.number_input('Actual completion (%)', min_value=0.0, max_value=100.0,
                                      step=1.0, value=float(row['actual_pct']))
            saved = st.form_submit_button('Save progress in this session')
        if saved:
            records = st.session_state['current_core']
            candidate = records['activities'].copy()
            mask = candidate['activity_id'].astype(str).eq(activity_id) & candidate['project_id'].astype(str).eq(pid)
            if int(mask.sum()) != 1:
                st.error('Activity not found in the selected project')
            else:
                candidate.loc[mask, 'actual_pct'] = float(new_pct)
                try:
                    candidate = validated_frame('activities', candidate)
                    proposed = dict(records, activities=candidate)
                    compute(select_project(proposed, pid))
                    overrides = dict(st.session_state.get('overrides', {}))
                    overrides['activities'] = candidate
                    st.session_state['overrides'] = overrides
                    log_session_change('activities', activity_id, 'progress updated', pid)
                    st.rerun()
                except (ValueError, TypeError, KeyError) as ex:
                    st.error(f'Update rejected: {ex}')
    st.caption('Baseline completion is modeled linearly; schedule analysis is illustrative.')


def show_schedule_gantt(result: dict) -> None:
    """Interactive, baseline-scoped Gantt with filters and detail navigation."""
    activities = result['activities']
    kpi = result['kpi']
    m1, m2, m3 = st.columns(3)
    m1.metric('Scheduled activities', len(activities))
    m2.metric('Behind baseline >10 pp', int(kpi['slipping_activities']))
    m3.metric('Physical completion', f"{kpi['actual_pct']:.1f}%")
    st.markdown('### Gantt · project schedule')
    st.caption('Bar length = baseline start–finish window; coloured fill = reported % complete '
               '(not recorded actual work dates). The dashed line is the project reporting date.')
    owners = sorted(activities['owner'].dropna().astype(str).unique().tolist())
    f1, f2 = st.columns(2)
    with f1:
        owner = st.selectbox('Filter owner', ['All owners'] + owners,
                             key=f'gantt_owner_{result["info"]["project_id"]}')
    with f2:
        status = st.selectbox('Filter status',
                              ['All activities', 'Behind baseline', 'Past finish date',
                               'In progress', 'Not started', 'Completed'],
                              key=f'gantt_status_{result["info"]["project_id"]}')
    shown = gantt_rows(activities, result['date'])
    if owner != 'All owners':
        shown = shown.loc[shown['owner'].astype(str).eq(owner)]
    if status != 'All activities':
        shown = shown.loc[shown['gantt_status'].eq(status)]
    st.caption(f'{len(shown)} of {len(activities)} activities shown · Hover to inspect dates, owner and progress; drag to zoom.')
    if shown.empty:
        st.info('No activities match these filters. Change the owner or status selection.')
    else:
        st.plotly_chart(gantt_figure(shown, result['date']),
                        use_container_width=True, key='schedule_full_gantt',
                        config={'displaylogo': False})
        ids = shown['activity_id'].astype(str).tolist()
        labels = {str(row['activity_id']): f"{row['wbs']} · {row['activity']}" for _, row in shown.iterrows()}
        c1, c2 = st.columns([3,1])
        with c1:
            choice = st.selectbox('Activity details', ids, format_func=lambda value: labels[value],
                                  key=f'gantt_choice_{result["info"]["project_id"]}')
        with c2:
            st.write('')
            st.button('Open activity →', key='gantt_open_activity',
                      on_click=open_activity_record, args=(choice,), use_container_width=True)
        st.download_button('Export displayed timeline CSV',
                           safe_csv(shown[['activity_id','wbs','activity','owner','start_date','finish_date',
                                  'planned_pct','actual_pct','variance_pp','gantt_status']]),
                           file_name=f'PEIMS_{result["info"]["project_id"]}_Gantt.csv',
                           mime='text/csv')
    st.caption('For dependency links, critical-path analysis and network finish dates, choose **Analysis**. '
               'This demo has no actual start/finish history, approved revised baseline, or resource-levelled schedule.')


def show_schedule_journey(result: dict) -> None:
    view = st.radio('Schedule view', ['Gantt', 'Activities', 'Analysis'], horizontal=True,
                    key='schedule_mode', help='Explore the Gantt, activity details, or deeper CPM analytics')
    if view == 'Gantt':
        show_schedule_gantt(result)
        return
    if view == 'Analysis':
        show_schedule(result)
        return
    activities = result['activities']
    record_id = st.session_state.get('peims_activity_detail')
    matching = activities.loc[activities['activity_id'].astype(str).eq(str(record_id))]
    if not matching.empty:
        show_activity_details(result, matching.iloc[0])
        return
    st.session_state.pop('peims_activity_detail', None)
    cols = st.columns(3)
    cols[0].metric('Activities', len(activities))
    cols[1].metric('Behind baseline >10 pp', result['kpi']['slipping_activities'])
    cols[2].metric('Schedule performance', f"{result['kpi']['spi']:.2f}" if result['kpi']['spi'] is not None else 'N/A')
    search = st.text_input('Find an activity', placeholder='Search by activity, WBS or owner', key='activity_search')
    filtered = activities.sort_values(['variance_pp', 'wbs'])
    if search.strip():
        token = search.casefold().strip()
        filtered = filtered.loc[filtered.apply(lambda r: token in f"{r['activity']} {r['wbs']} {r['owner']}".casefold(), axis=1)]
    st.caption(f'Select an activity to open its details · {len(filtered)} shown')
    if filtered.empty:
        st.info('No activities match this search.')
    for _, row in filtered.iterrows():
        with st.container(key=f'peims_record_activity_{row["activity_id"]}'):
            status = activity_status(row)
            st.button(f'{row["wbs"]}  {row["activity"]}  ·  {float(row["actual_pct"]):.0f}% complete  ·  {status}  →',
                      key=f'view_activity_{row["activity_id"]}',
                      on_click=open_activity_record, args=(str(row['activity_id']),),
                      use_container_width=True)
    st.caption('For dependency modeling, critical path and the complete register, select Analysis above.')


def show_cost_journey(result: dict) -> None:
    view = st.radio('Cost view', ['Overview', 'Detailed analysis'], horizontal=True, key='cost_view')
    if view == 'Detailed analysis':
        show_financials(result)
        return
    k, currency = result['kpi'], result['info']['currency']
    a, b, c = st.columns(3)
    a.metric('Budget at completion', money(k['budget'], currency))
    b.metric('Recorded costs', money(k['actual_cost'], currency))
    c.metric('Cost efficiency (CPI)', f'{k["cpi"]:.2f}' if k['cpi'] is not None else 'N/A')
    st.markdown('### Cost outlook')
    fc = cost_forecast(k['budget'], k['earned_value'], k['actual_cost'], k['committed_cost'])
    if fc['eac_cpi'] is None:
        st.info('No cost forecast is available from the current project record.')
    else:
        st.metric('Illustrative estimate at completion', money(fc['eac_cpi'], currency))
        st.caption('This is a CPI-continuation scenario, not an approved project forecast.')
    st.markdown('### Work packages')
    summary = result['activities'][['activity', 'baseline_budget', 'actual_cost']].copy()
    summary.columns = ['Work package', 'Budget', 'Recorded cost']
    st.dataframe(summary, hide_index=True, use_container_width=True)
    st.caption('Select Detailed analysis for earned-value bridges, exposure charts and model assumptions.')


def show_procurement_journey(result: dict) -> None:
    view = st.radio('Procurement view', ['Orders', 'Analysis'], horizontal=True, key='procurement_view')
    if view == 'Analysis':
        show_procurement(result)
        return
    p = result['procurement']
    a, b, c = st.columns(3)
    a.metric('Purchase orders', len(p))
    b.metric('Overdue deliveries', result['kpi']['overdue_po'])
    c.metric('Critical overdue', result['kpi']['critical_overdue_po'])
    order_id = st.session_state.get('peims_order_detail')
    found = p.loc[p['po_id'].astype(str).eq(str(order_id))]
    if not found.empty:
        if st.button('← All orders', key='back_to_orders'):
            st.session_state.pop('peims_order_detail', None)
            st.rerun()
        row = found.iloc[0]
        st.markdown(f'### {row["item"]}')
        st.caption(f'PURCHASE ORDER · {row["po_id"]}')
        with st.container(border=True):
            st.write(f'**Supplier:** {row["supplier"]}')
            st.write(f'**Status:** {row["status"]}')
            st.write(f'**Expected delivery:** {pd.Timestamp(row["expected_date"]):%d %b %Y}')
            st.write(f'**Order value:** {money(row["po_value"], result["info"]["currency"])}')
            st.write(f'**Critical:** {row["critical"]} · **Overdue:** {bool(row["overdue"])}')
        st.caption('Purchase order data is fictional; no live supplier integration.')
        return
    st.session_state.pop('peims_order_detail', None)
    st.markdown('### Orders and deliveries')
    for _, row in p.sort_values(['overdue', 'expected_date'], ascending=[False, True]).iterrows():
        label = f'{row["po_id"]}  ·  {row["item"]}  ·  {row["status"]}'
        st.button(label + '  →', key=f'open_order_{row["po_id"]}',
                  on_click=set_order_detail, args=(str(row['po_id']),), use_container_width=True)
    st.caption('Select Analysis for the delivery exposure visualization and full register.')


def set_order_detail(order_id: str) -> None:
    st.session_state['peims_order_detail'] = order_id


def update_demo_action_status(project_id: str, action_id: str, status: str) -> None:
    """Write to existing session overrides only, validating the whole action register."""
    if status not in ('Open', 'In progress', 'Closed'):
        raise ValueError('Unsupported action status')
    records = st.session_state['current_core']
    df = records['actions'].copy()
    mask = df['project_id'].astype(str).eq(project_id) & df['action_id'].astype(str).eq(action_id)
    if int(mask.sum()) != 1:
        raise ValueError('Action not found for this project')
    df.loc[mask, 'status'] = status
    df = validated_frame('actions', df)
    overrides = dict(st.session_state.get('overrides', {}))
    overrides['actions'] = df
    st.session_state['overrides'] = overrides
    log_session_change('actions', action_id, f'status set to {status}', project_id)


def show_issues_journey(result: dict) -> None:
    view = st.radio('Issues view', ['Actions', 'Analysis'], horizontal=True, key='issues_mode')
    if view == 'Analysis':
        show_risks(result)
        return
    actions = result['actions']
    a, b, c = st.columns(3)
    a.metric('Action items', len(actions))
    b.metric('Overdue actions', result['kpi']['overdue_actions'])
    c.metric('High risks', result['kpi']['open_high_risks'])
    action_id = st.session_state.get('peims_action_detail')
    found = actions.loc[actions['action_id'].astype(str).eq(str(action_id))]
    if not found.empty:
        if st.button('← All actions', key='back_to_actions'):
            st.session_state.pop('peims_action_detail', None)
            st.rerun()
        row = found.iloc[0]
        st.caption(f'ACTION · {row["action_id"]}')
        st.markdown(f'### {row["action"]}')
        with st.container(border=True):
            st.write(f'**Assigned to:** {row["owner"]}')
            st.write(f'**Due:** {pd.Timestamp(row["due_date"]):%d %b %Y}')
            st.write(f'**Priority:** {row["priority"]} · **Status:** {row["status"]}')
            st.write(f'**Source:** {row["source"]}')
            st.caption('This is a demonstration status update, not a workflow approval.')
            pid = str(result['info']['project_id'])
            if str(row['status']) != 'Closed':
                st.button('Mark completed', key=f'close_action_{action_id}',
                          on_click=update_demo_action_status, args=(pid, str(action_id), 'Closed'))
            else:
                st.button('Reopen action', key=f'reopen_action_{action_id}',
                          on_click=update_demo_action_status, args=(pid, str(action_id), 'Open'))
        return
    st.session_state.pop('peims_action_detail', None)
    st.markdown('### Action queue')
    for _, row in priority_actions(result, limit=100).iterrows():
        label = f'{row["priority"]} · {row["action"]} · {row["status"]}'
        st.button(label + '  →', key=f'open_action_{row["action_id"]}',
                  on_click=open_action_record, args=(str(row['action_id']),), use_container_width=True)
    st.caption('Select Analysis for the full risk matrix and action register.')


def show_documents_journey(core: dict, workflows: dict, project_id: str, snapshot_date) -> None:
    valid_projects = set(core['projects']['project_id'].astype(str))
    docs = workflows['documents'].loc[workflows['documents']['project_id'].astype(str).eq(project_id)].copy()
    st.metric('Engineering records', len(docs))
    document_id = st.session_state.get('peims_document_detail')
    found = docs.loc[docs['document_id'].astype(str).eq(str(document_id))]
    if not found.empty:
        if st.button('← All documents', key='back_to_documents'):
            st.session_state.pop('peims_document_detail', None)
            st.rerun()
        row = found.iloc[0]
        st.caption(f'DOCUMENT · {row["document_id"]}')
        st.markdown(f'### {row["title"]}')
        with st.container(border=True):
            for field, label in [('revision','Revision'), ('status','Review status'),
                                 ('discipline','Discipline'), ('owner','Owner'),
                                 ('reference','Reference')]:
                st.write(f'**{label}:** {row[field]}')
        st.info('Metadata only. This demonstration does not store or display original drawing files.')
        return
    st.session_state.pop('peims_document_detail', None)
    st.markdown('### Drawing and document register')
    st.caption('Select a record to inspect details. No uploaded drawing files are stored.')
    for _, row in docs.sort_values(['discipline','title']).iterrows():
        st.button(f'{row["title"]} · Rev {row["revision"]} · {row["status"]}  →',
                  key=f'view_document_{row["document_id"]}',
                  on_click=open_document_record, args=(str(row['document_id']),),use_container_width=True)
    st.markdown('### Manage register')
    show_register_editor('documents', workflows, project_id, valid_projects, snapshot_date)


def show_overview(result: dict):
    k, info = result["kpi"], result["info"]
    # The special container enables a responsive 4→2→1 KPI grid without
    # disrupting unrelated layouts in other project workspaces.
    with st.container(key="peims_overview_kpis"):
        a, b, c, d = st.columns(4)
        a.metric("Physical progress", f"{k['actual_pct']:.1f}%", f"{k['progress_gap']:+.1f} pp vs baseline")
        b.metric("Schedule index (SPI)", f"{k['spi']:.2f}" if k['spi'] is not None else 'N/A')
        c.metric("Cost index (CPI)", f"{k['cpi']:.2f}" if k['cpi'] is not None else 'N/A')
        d.metric("High-priority risks", k['open_high_risks'])
    st.subheader('Project Gantt · schedule and reported progress')
    st.plotly_chart(gantt_figure(result['activities'], result['date']),
                    use_container_width=True, key='command_centre_gantt',
                    config={'displayModeBar': False, 'displaylogo': False})
    st.caption('Grey: scheduled window · coloured fill: reported completion fraction · '
               'dashed line: reporting date. This view does not infer actual dates or an approved revised baseline.')
    st.button('Explore Gantt and activity details →', key='command_open_gantt',
              on_click=open_gantt_workspace, use_container_width=True)
    left, right = st.columns([1.65, 1], gap="large")
    with left:
        st.subheader("Progress S-curve · reported vs baseline")
        st.plotly_chart(progress_s_curve(result['history'], result['date']), use_container_width=True)
        st.caption("Weekly progress snapshots only. This is a descriptive trend, not a completion forecast. Activity KPIs use the current weighted register and may differ from the last historical point.")
    with right:
        st.subheader("Executive interpretation")
        for statement in insight_summary(result):
            st.markdown(f"• {statement}")
        st.divider()
        st.metric("Overdue deliveries", k['overdue_po'])
        st.metric("Overdue actions", k['overdue_actions'])
    st.subheader("Priority exception register")
    flags_panel(make_alerts(result)[:5])
    if 'pm_tasks' in st.session_state:
        pid=str(info['project_id'])
        task_kpi=task_metrics(st.session_state['pm_tasks'],st.session_state['pm_time_logs'],pid,result['date'])
        st.markdown('#### Work-item status')
        x,y,z=st.columns(3)
        x.metric('Open tasks',task_kpi['open'])
        y.metric('Overdue tasks',task_kpi['overdue'])
        z.metric('Logged demo hours',f"{task_kpi['logged_hours']:.1f} h")
        st.button('Manage tasks and milestones →',key='overview_pm_open',
                  on_click=change_workspace,args=('Work management',),use_container_width=True)

def show_schedule(result: dict):
    acts, k = result["activities"], result["kpi"]
    a, b, c = st.columns(3)
    a.metric("Tracked activities", len(acts))
    b.metric("Slipping >10 percentage points", k["slipping_activities"])
    c.metric("Schedule performance index", f"{k['spi']:.2f}" if k["spi"] is not None else "N/A")
    st.subheader("Activity completion · variance dumbbells")
    st.plotly_chart(schedule_variance(acts), use_container_width=True)
    st.caption("Open circle = linear baseline; solid circle = actual completion. Red marks activities >10 pp behind. Sort prioritizes the largest negative gap toward the bottom.")
    st.subheader("Dependency model · illustrative CPM")
    try:
        pid = str(result['info']['project_id'])
        links = get_sample_dependencies()
        links = links.loc[links['project_id'].eq(pid)].copy()
        cpm = critical_path(acts, links)
        c1, c2, c3 = st.columns(3)
        c1.metric('Modelled network finish', cpm['model_finish'])
        c2.metric('Critical activities', len(cpm['critical_activity_ids']))
        c3.metric('Finish-to-start links', len(links))
        st.plotly_chart(dependency_timeline(acts, cpm, result['date']), use_container_width=True)
        st.caption('Red = zero-float activity in the limited CPM model; blue = noncritical. Dates reflect calendar-day dependencies and baseline no-earlier-than starts, not a recovered/validated P6 schedule.')
        with st.expander('Critical path calculation and export'):
            network = pd.DataFrame(cpm['activities']).merge(acts[['activity_id','activity']], on='activity_id', how='left')
            st.dataframe(network[['activity_id','activity','earliest_start','earliest_finish','total_float_days','critical']], use_container_width=True, hide_index=True)
            st.download_button('Export CPM model CSV', network.to_csv(index=False),
                               file_name=f'PEIMS_CPM_{pid}.csv', mime='text/csv')
            st.caption(cpm['assumptions'])
    except (ValueError, KeyError, TypeError) as ex:
        st.warning(f'Dependency model unavailable for current session records: {ex}')
    st.subheader("Activity control register")
    show = acts.sort_values('wbs').copy()
    show['start_date'] = show['start_date'].dt.strftime('%Y-%m-%d')
    show['finish_date'] = show['finish_date'].dt.strftime('%Y-%m-%d')
    st.dataframe(df_display(show, {'wbs':'WBS', 'activity':'Activity', 'owner':'Owner',
                                   'start_date':'Baseline start', 'finish_date':'Baseline finish',
                                   'planned_pct':'Planned %', 'actual_pct':'Actual %',
                                   'variance_pp':'Gap (pp)', 'is_late':'Past baseline finish'}),
                 use_container_width=True, hide_index=True)
    st.download_button('Export activity controls CSV', acts.to_csv(index=False),
                       file_name='activity_controls.csv', mime='text/csv')



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
    k, currency, acts = result['kpi'], result['info']['currency'], result['activities']
    cols = st.columns(4)
    cols[0].metric('Budget at completion (BAC)', money(k['budget'], currency))
    cols[1].metric('Actual cost (AC)', money(k['actual_cost'], currency))
    cols[2].metric('Earned value (EV)', money(k['earned_value'], currency))
    cols[3].metric('Cost efficiency (CPI)', f"{k['cpi']:.2f}" if k['cpi'] is not None else 'N/A')
    left, right = st.columns([1.35,1], gap='large')
    with left:
        st.subheader('Cost variance bridge · AC → EV')
        st.plotly_chart(cost_variance_waterfall(k, currency), use_container_width=True)
        st.caption('Waterfall reconciles recorded AC to earned value through cost variance (EV − AC). It is not a cash-flow statement.')
    with right:
        st.subheader('Earned value signals')
        st.metric('Cost variance (CV = EV − AC)', money(k['cost_variance'], currency))
        st.metric('Schedule variance (SV = EV − PV)', money(k['schedule_variance_value'], currency))
        st.metric('Committed, not yet actual', money(k['committed_cost'], currency))
        st.caption('Commitments are separately disclosed; they are not added to AC.')
    st.subheader('Estimate at completion · CPI-continuation scenario')
    try:
        fc=cost_forecast(k['budget'], k['earned_value'], k['actual_cost'], k['committed_cost'])
        a,b,c=st.columns(3)
        a.metric('Estimate at completion (EAC)', money(fc['eac_cpi'], currency) if fc['eac_cpi'] is not None else 'N/A')
        b.metric('Estimate to complete (ETC)', money(fc['etc_cpi'], currency) if fc['etc_cpi'] is not None else 'N/A')
        c.metric('Variance at completion (VAC)', money(fc['vac_cpi'], currency) if fc['vac_cpi'] is not None else 'N/A')
        st.caption(fc['method'] + ' Illustration only; depends on approved physical progress and verified actuals.')
    except ValueError as ex:
        st.warning(f'Forecast unavailable: {ex}')
    st.subheader('Work-package exposure · schedule versus cost')
    st.plotly_chart(cost_exposure_quadrant(acts, currency), use_container_width=True)
    st.caption('Each bubble is one activity; size represents baseline budget. Bottom-left contains activities both behind baseline and with negative cost variance. The figure is diagnostic, not a causal inference.')
    with st.expander('Metric definitions and limitations'):
        st.markdown('**EV** = baseline budget × verified actual completion. **PV** = budget × modelled planned completion. **AC** = recorded expenditure. **CPI** = EV / AC and **SPI** = EV / PV. Planned completion is assumed linear between baseline dates. These are provisional project controls, not a validated financial ledger.')

def show_procurement(result: dict):
    p = result['procurement'].copy()
    a,b,c=st.columns(3)
    a.metric('Open purchase orders', int((~p['received']).sum()))
    b.metric('Overdue deliveries', int(p['overdue'].sum()))
    c.metric('Critical overdue', result['kpi']['critical_overdue_po'])
    st.subheader('Delivery exposure · timing × committed order value')
    st.plotly_chart(procurement_delivery_map(p, result['date'], result['info']['currency']), use_container_width=True)
    st.caption('Vertical dashed line = reporting cut-off. Bubble area increases with PO value; red = critical and overdue, amber = overdue. These order values are not necessarily costs incurred.')
    st.subheader('Delivery exceptions')
    late=p.loc[p['overdue']].sort_values(['days_late','po_value'], ascending=[False, False])
    if late.empty:
        st.success('No outstanding past-due purchase orders in this snapshot.')
    else:
        for _,row in late.iterrows():
            st.warning(f"{row['po_id']} — {row['item']}: {int(row['days_late'])} days overdue; critical: {row['critical']}; contact {row['supplier']}.")
    st.subheader('Procurement detail')
    p['expected_date']=p['expected_date'].dt.strftime('%Y-%m-%d')
    p['received_date']=p['received_date'].dt.strftime('%Y-%m-%d').fillna('—')
    st.dataframe(df_display(p, {'po_id':'PO', 'item':'Item', 'supplier':'Supplier', 'status':'Status',
                                'expected_date':'Expected', 'received_date':'Received',
                                'po_value':'PO value', 'critical':'Critical', 'days_late':'Days late'}),
                 use_container_width=True, hide_index=True)

def show_risks(result: dict):
    risks, actions = result['risks'], result['actions']
    a,b,c=st.columns(3)
    a.metric('Open risks', int(risks['open'].sum()))
    b.metric('High risks', result['kpi']['open_high_risks'])
    c.metric('Overdue actions', result['kpi']['overdue_actions'])
    left,right=st.columns([.92,1.08],gap='large')
    with left:
        st.subheader('Risk severity matrix · P × I')
        st.plotly_chart(risk_severity_matrix(risks), use_container_width=True)
        st.caption('Background colour reflects probability × impact score, while each cell label counts OPEN risks in that cell. Closed risks are excluded. Site-approved risk thresholds take precedence.')
    with right:
        st.subheader('Priority action register')
        acts=actions.copy().sort_values(['overdue','due_date'],ascending=[False,True])
        acts['due_date']=acts['due_date'].dt.strftime('%Y-%m-%d')
        st.dataframe(df_display(acts, {'action_id':'ID', 'action':'Action', 'owner':'Owner',
                                       'due_date':'Due', 'priority':'Priority', 'status':'Status',
                                       'overdue':'Overdue'}),use_container_width=True,hide_index=True,height=440)
    st.subheader('Detailed risk register')
    st.dataframe(df_display(risks.sort_values('score',ascending=False),
                            {'risk_id':'ID','risk':'Risk','category':'Area','probability':'P',
                             'impact':'I','score':'Score','level':'Level', 'status':'Status',
                             'owner':'Owner','mitigation':'Mitigation'}),
                 use_container_width=True,hide_index=True)


def show_analytics(result: dict):
    """Cross-discipline analytical exploration; respects the active project."""
    st.subheader('Analytical studio · linked project signals')
    st.caption('Visualize work-package relationships with a real project/owner filter. Values come from the current project snapshot; no predictive AI is applied.')
    acts=result['activities']
    owners=['All owners']+sorted(acts['owner'].dropna().astype(str).unique().tolist())
    selected_owner=st.selectbox('Work-package owner', owners, key='analytics_owner')
    filtered=acts if selected_owner=='All owners' else acts.loc[acts['owner'].eq(selected_owner)]
    a,b,c=st.columns(3)
    a.metric('Selected activities', len(filtered))
    a_gap=float((filtered['actual_pct']*filtered['weight']).sum()/filtered['weight'].sum()-(filtered['planned_pct']*filtered['weight']).sum()/filtered['weight'].sum()) if not filtered.empty and filtered['weight'].sum()>0 else 0.0
    b.metric('Selected physical progress gap', f'{a_gap:+.1f} pp')
    c.metric('Selected cost variance', money(float((filtered['earned_value']-filtered['actual_cost']).sum()),result['info']['currency']))
    l,r=st.columns([1.15,1],gap='large')
    with l:
        st.markdown('**Schedule performance · selected work packages**')
        st.plotly_chart(schedule_variance(filtered), use_container_width=True, key="analytics_schedule_variance")
    with r:
        st.markdown('**Financial exposure · selected work packages**')
        st.plotly_chart(cost_exposure_quadrant(filtered,result['info']['currency']), use_container_width=True, key='analytics_cost_exposure')
    st.caption('Drill-down filter applies only to the two analytical charts and selected-owner KPI cards. Main project reports remain based on the complete project data.')
    st.dataframe(df_display(filtered.sort_values('variance_pp'),
                 {'activity_id':'ID','activity':'Activity','owner':'Owner',
                  'variance_pp':'Progress gap (pp)','baseline_budget':'Baseline budget',
                  'earned_value':'Earned value','actual_cost':'Actual cost'}),
                 use_container_width=True,hide_index=True)



def show_reports(result: dict, workflows: dict[str, pd.DataFrame] | None = None):
    st.subheader("Draft weekly engineering report")
    st.info("Rule-based draft report for engineering review. Not an approved document or generative-AI output.")
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
    st.info("Sandbox editing: changes exist only in this session. Use the workspace ZIP backup to retain fictional updates.")
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



def _sheet_select_configs(core: dict, workflows: dict, sheet: str, project_id: str) -> dict:
    """Offer reusable values in the grid, without restricting free-text mode."""
    configs = {}
    for field in SUGGESTED_FIELDS.get(sheet, ()):
        opts = suggestions(core, workflows, sheet, project_id, field)
        if opts:
            configs[field] = st.column_config.SelectboxColumn(
                field.replace('_', ' ').title(),
                options=opts,
                help='Previously entered values for this project. Switch to Free text for a new option.',
            )
    return configs


def _entry_widget(field: str, sheet: str, project_id: str, core: dict, workflows: dict,
                  snapshot: pd.Timestamp):
    """Render a form control, preferring searchable suggestions for repeated fields."""
    label = field.replace('_', ' ').title()
    if field in SUGGESTED_FIELDS.get(sheet, ()):
        opts = suggestions(core, workflows, sheet, project_id, field)
        fixed = field in ('critical', 'priority', 'status')
        defaults = {'status': {'actions':'Open', 'risks':'Open', 'procurement':'Ordered',
                               'contractors':'Active', 'rfis':'Open', 'documents':'Draft'},
                    'priority': {'actions':'Medium'},
                    'critical': {'procurement':'No', 'rfis':'No'}}
        chosen = defaults.get(field, {}).get(sheet)
        idx = opts.index(chosen) if chosen in opts else None
        return st.selectbox(label, opts, index=idx,
                            accept_new_options=not fixed,
                            placeholder='Choose a previous value or type a new one' if not fixed else 'Choose an option',
                            help='Suggestions come only from this project. New values are saved with your record.'
                                 if not fixed else 'Select a recognized value.')
    if field in ('start_date', 'finish_date', 'due_date', 'expected_date',
                 'opened_on', 'planned_finish', 'updated_on'):
        shift = 14 if field in ('finish_date', 'expected_date', 'planned_finish') else (7 if field=='due_date' else 0)
        return st.date_input(label, value=(snapshot + pd.Timedelta(days=shift)).date())
    if field in ('weight', 'actual_pct', 'baseline_budget', 'po_value',
                 'progress_pct', 'probability', 'impact'):
        if field in ('probability','impact'):
            return st.selectbox(label+' (1–5)', [1, 2, 3, 4, 5], index=None,
                                placeholder='Assess this risk (required)')
        upper = 100.0 if field in ('actual_pct','progress_pct') else None
        return st.number_input(label, min_value=0.0, max_value=upper,
                               value=1.0 if field == 'weight' else 0.0,
                               step=1.0 if field in ('actual_pct','progress_pct') else 0.1)
    if field == 'wbs':
        frame = project_sheet(core, workflows, sheet, project_id)
        values = pd.to_numeric(frame.get('wbs', pd.Series(dtype=float)), errors='coerce')
        default = round(float(values.max()) + .1, 2) if values.notna().any() else 1.0
        return st.number_input('WBS code', min_value=0.0, value=default, step=0.1, format='%.2f')
    if field == 'received_date':
        return None  # Optional until the order is marked Received.
    if field in ('mitigation', 'notes', 'response_summary','scope'):
        return st.text_area(label, height=80)
    return st.text_input(label, placeholder='Enter '+label.lower())


def show_smart_add(core: dict, workflows: dict, sheet: str, project_id: str) -> None:
    """Accessible single-record entry with suggestions; saves through apply_sheet."""
    if sheet not in SUGGESTED_FIELDS:
        return
    st.markdown('#### Add an entry with suggestions')
    st.caption('Reusable values appear as searchable choices. You can also type a new owner, '
               'discipline, supplier or category. All changes remain within this browser session.')
    expected = WORKFLOW_COLUMNS.get(sheet, DATASET_COLUMNS.get(sheet))
    pk = SHEET_KEYS[sheet]
    project_rows = project_sheet(core, workflows, sheet, project_id)
    snapshot = pd.Timestamp(core['projects'].loc[core['projects']['project_id'].astype(str).eq(project_id),
                                                 'snapshot_date'].iloc[0]).normalize()
    version = st.session_state.get('smart_add_version', 0)
    with st.form(f'smart_add_{project_id}_{sheet}_{version}', clear_on_submit=False):
        st.write('**New record details**')
        record_id = st.text_input(pk.replace('_',' ').title(),
                                  value=new_record_id(core, workflows, sheet, project_id),
                                  help='Suggested unique ID; you can change it before saving.')
        fields = [f for f in expected if f not in (pk,'project_id','received_date')]
        output = {}
        left, right = st.columns(2)
        for i, field in enumerate(fields):
            with (left if i%2 == 0 else right):
                output[field] = _entry_widget(field, sheet, project_id, core, workflows, snapshot)
        if sheet == 'procurement':
            received_date = st.date_input('Received date (used only when status is Received)', value=snapshot.date())
            output['received_date'] = received_date if output.get('status') == 'Received' else None
        submit = st.form_submit_button('Add record to this project', type='primary')
    if submit:
        try:
            row = validate_smart_inputs(sheet, {**output, pk:record_id.strip(), 'project_id':project_id})
            created = pd.concat([project_rows, pd.DataFrame([row])], ignore_index=True)
            new_core, new_workflows, events = apply_sheet(core, workflows, sheet, project_id, created)
            if sheet in WORKFLOW_COLUMNS:
                overrides = dict(st.session_state.get('workflow_overrides', {}))
                overrides[sheet] = new_workflows[sheet]
                st.session_state['workflow_overrides'] = overrides
            else:
                overrides = dict(st.session_state.get('overrides', {}))
                overrides[sheet] = new_core[sheet]
                if sheet=='activities':
                    overrides['costs'] = new_core['costs']
                st.session_state['overrides'] = overrides
            history = list(st.session_state.get('change_history', []))
            st.session_state['change_history'] = (history + events)[-250:]
            st.session_state['smart_add_version'] = version+1
            st.session_state['studio_edit_version'] = st.session_state.get('studio_edit_version', 0)+1
            st.success(f'Created {record_id} in {sheet}.')
            st.rerun()
        except (ValueError, TypeError, KeyError) as exc:
            st.error(f'New record was not saved: {exc}')


def show_spreadsheet_studio(core: dict, workflows: dict, project_id: str, result: dict) -> None:
    """Excel-inspired register workspace; BI-style analysis; vetted XLSX exchange.

    This is a typed, project-scoped record editor. It deliberately does not
    execute spreadsheet formulas or provide a general-purpose Excel engine.
    """
    st.caption('Fictional records only · Changes affect this browser session, not a shared database')
    sheet = st.selectbox(
        'Open worksheet', SHEET_NAMES, format_func=lambda n: SHEET_LABELS[n], key='studio_sheet')
    sheet_frame = project_sheet(core, workflows, sheet, project_id)
    a, b, c = st.columns(3)
    a.metric('Rows in this project', len(sheet_frame))
    b.metric('Columns', len(sheet_frame.columns))
    c.metric('Workspace', 'Editable' if sheet in EDITABLE_SHEETS else 'Read-only')
    tab_grid, tab_analysis, tab_excel = st.tabs(['Worksheet grid', 'Analysis builder', 'Excel exchange'])

    with tab_grid:
        st.markdown('#### Project worksheet')
        st.caption('Use the spreadsheet grid for bulk edits or **Add an entry with suggestions** below it. '
                   'Existing rows cannot be deleted or renamed. New entries must pass validation.')
        if sheet in EDITABLE_SHEETS:
            st.caption('Suggestion source: this project only. Approved organization-wide entries require the authenticated enterprise service, which is not connected to this demo.')
            dropdowns = st.toggle('Suggest previously used values in grid', value=True,
                                  key=f'studio_suggestions_{project_id}_{sheet}',
                                  help='Switch off to type a brand-new category or owner directly in the grid.')
            edit_key = f'studio_grid_{project_id}_{sheet}_{dropdowns}_{st.session_state.get("studio_edit_version", 0)}'
            with st.form(f'studio_form_{project_id}_{sheet}', border=False):
                opts = {'use_container_width': True, 'hide_index': True,
                        'height': 420, 'num_rows': 'fixed' if sheet == 'costs' else 'dynamic',
                        'disabled': ['project_id'] if sheet != 'costs'
                        else ['project_id', SHEET_KEYS[sheet]]}
                if dropdowns:
                    opts['column_config'] = _sheet_select_configs(core, workflows, sheet, project_id)
                editable = st.data_editor(sheet_frame, key=edit_key, **opts)
                submit = st.form_submit_button('Validate & apply worksheet changes', type='primary')
            if sheet == 'costs':
                st.info('Add a new activity in **Activities & WBS** first. PEIMS automatically creates its cost ledger row with zero actual and committed expenditure.')
            else:
                st.caption('For a new row, enter a unique ID in the first column and fill the remaining fields. '
                           'Leave project_id blank; PEIMS links it to this project when saving.')
            if submit:
                try:
                    new_core, new_workflows, events = apply_sheet(core, workflows, sheet, project_id, editable)
                    if not events:
                        st.info('No changes were found.')
                    else:
                        if sheet in new_core and sheet not in ('contractors', 'rfis', 'documents'):
                            overrides = dict(st.session_state.get('overrides', {}))
                            overrides[sheet] = new_core[sheet]
                            if sheet == 'activities':
                                overrides['costs'] = new_core['costs']
                            st.session_state['overrides'] = overrides
                        else:
                            overrides = dict(st.session_state.get('workflow_overrides', {}))
                            overrides[sheet] = new_workflows[sheet]
                            st.session_state['workflow_overrides'] = overrides
                        history = list(st.session_state.get('change_history', []))
                        st.session_state['change_history'] = (history + events)[-250:]
                        st.session_state['studio_edit_version'] = st.session_state.get('studio_edit_version', 0) + 1
                        st.success(f'Applied {len(events)} record change(s) to this session.')
                        st.rerun()
                except (ValueError, KeyError, TypeError) as exc:
                    st.error(f'Worksheet rejected: {exc}')
        else:
            st.dataframe(sheet_frame, use_container_width=True, hide_index=True, height=420)
            st.info('Historical progress snapshots are read-only in this release.')
        if sheet in SUGGESTED_FIELDS:
            with st.expander('＋ Add an entry with suggestions', expanded=False):
                show_smart_add(core, workflows, sheet, project_id)
        if sheet == 'activities':
            with st.expander('Calculated columns (read-only)', expanded=False):
                calc = result['activities'][['wbs', 'activity', 'planned_pct', 'actual_pct', 'variance_pp', 'earned_value']]
                st.dataframe(calc, use_container_width=True, hide_index=True)
                st.caption('These columns are calculated by PEIMS rather than Excel cell formulas.')
        st.download_button('Export this sheet as CSV', safe_csv(sheet_frame),
                           file_name=f'PEIMS_{project_id}_{sheet}.csv', mime='text/csv')

    with tab_analysis:
        st.markdown('#### Build an analytical view')
        st.caption('Choose a dataset, group your records, and apply a filter. Results come from the same '
                   'validated project records used by the dashboard.')
        source = st.selectbox('Dataset', tuple(SOURCE_SPECS), key='studio_bi_source')
        spec = SOURCE_SPECS[source]
        left, right = st.columns(2)
        with left:
            dimension = st.selectbox('Group by', spec['dimensions'], key=f'studio_dim_{source}')
        with right:
            metric = st.selectbox('Measure', spec['metrics'], key=f'studio_measure_{source}')
        filter_fields = ('All records',) + spec['dimensions']
        filter_field = st.selectbox('Filter dimension', filter_fields, key=f'studio_filter_{source}')
        selected_value = None
        if filter_field != 'All records':
            items = sorted(source_frame(result, source)[filter_field].fillna('(blank)').astype(str).unique().tolist())
            selected_value = st.selectbox('Filter value', items, key=f'studio_filter_value_{source}_{filter_field}')
        try:
            summary, details = build_analysis(result, source, dimension, metric,
                                              None if filter_field == 'All records' else filter_field,
                                              selected_value)
            if summary.empty:
                st.info('No records match these filters.')
            else:
                fig = go.Figure(go.Bar(x=summary[dimension], y=summary[metric],
                                       hovertemplate='%{x}: %{y:,.2f}<extra></extra>'))
                fig.update_layout(xaxis_title=dimension.replace('_', ' ').title(), yaxis_title=metric,
                                  margin=dict(t=18, b=20, l=12, r=12), height=330)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(summary, hide_index=True, use_container_width=True)
                st.download_button('Export analytical result CSV', safe_csv(summary),
                                   file_name=f'PEIMS_{project_id}_{source.lower()}_analysis.csv',
                                   mime='text/csv')
                with st.expander(f'View filtered source records ({len(details)})'):
                    st.dataframe(details, hide_index=True, use_container_width=True)
            st.caption('Grouped aggregates are descriptive, not Power BI semantic-model measures. '
                       'Weighted completion uses the project activity weights.')
        except (ValueError, KeyError) as exc:
            st.error(f'Analysis cannot be calculated: {exc}')

    with tab_excel:
        st.markdown('#### Excel workbook exchange')
        st.caption('Download a multi-worksheet Excel workbook. Edit existing rows or add new records '
                   'with unique IDs, then import one worksheet at a time. Existing IDs and project scopes are protected.')
        try:
            data = workbook_bytes(core, workflows, project_id)
            st.download_button('Download Excel workbook (.xlsx)', data,
                               file_name=f'PEIMS_{project_id}_ProjectWorkbook.xlsx',
                               mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception as exc:
            st.error(f'Could not generate workbook: {exc}')
        if sheet not in EDITABLE_SHEETS:
            st.info('Choose an editable worksheet above before importing.')
        else:
            file = st.file_uploader(f'Import updated {sheet}.xlsx worksheet', type=['xlsx'],
                                    key=f'studio_xlsx_upload_{sheet}')
            if file is not None:
                try:
                    imported = imported_sheet(file.getvalue(), sheet)
                    # Show a preview; validation uses the exact same path as in-app edits.
                    st.caption(f'Preview: {len(imported)} rows from worksheet {sheet}')
                    st.dataframe(imported.head(8), hide_index=True, use_container_width=True)
                    new_core, new_workflows, events = apply_sheet(core, workflows, sheet, project_id, imported)
                    st.info(f'{len(events)} existing record(s) would change. No records have been applied yet.')
                    if st.button('Confirm validated Excel import', type='primary', key=f'xlsx_apply_{sheet}'):
                        if events:
                            if sheet in new_core and sheet not in ('contractors', 'rfis', 'documents'):
                                edits = dict(st.session_state.get('overrides', {}))
                                edits[sheet] = new_core[sheet]
                                st.session_state['overrides'] = edits
                            else:
                                edits = dict(st.session_state.get('workflow_overrides', {}))
                                edits[sheet] = new_workflows[sheet]
                                st.session_state['workflow_overrides'] = edits
                            history = list(st.session_state.get('change_history', []))
                            st.session_state['change_history'] = (history + events)[-250:]
                            st.session_state['studio_edit_version'] = st.session_state.get('studio_edit_version', 0) + 1
                            st.success('Excel worksheet imported into this session.')
                            st.rerun()
                        else:
                            st.info('Imported sheet matches current records; nothing to change.')
                except (ValueError, TypeError, KeyError) as exc:
                    st.error(f'Excel import rejected: {exc}')
        st.warning('This is not full Excel, Power Query, or Power BI. Formula execution and '
                   'automatic database sync are not supported. Use only fictional or approved sample data.')


def main():
    base_data = get_demo_data()
    all_data = {name: st.session_state.get("overrides", {}).get(name, base_data[name]) for name in DATASET_COLUMNS}
    base_workflows = get_demo_workflows()
    workflows = {name: st.session_state.get("workflow_overrides", {}).get(name, base_workflows[name])
                 for name in WORKFLOW_COLUMNS}
    st.session_state["current_core"] = all_data

    # One explicit, accessible project selector and one stable workspace navigation menu.
    st.sidebar.markdown(render_brand(), unsafe_allow_html=True)
    st.sidebar.markdown('<div class="peims-sidebar-heading">ACTIVE PROJECT</div>', unsafe_allow_html=True)
    ps = all_data["projects"]
    chosen = st.sidebar.selectbox(
        "Active project", ps["project_id"].tolist(), label_visibility="collapsed",
        format_func=lambda p: ps.loc[ps["project_id"].eq(p), "project_name"].iloc[0],
        key="active_project",
    )
    st.sidebar.markdown('<div class="peims-sidebar-heading">WORKSPACE</div>', unsafe_allow_html=True)
    migrate_navigation_session()
    if st.session_state.get('_peims_gantt_view_migrated') != 'v0.6.4':
        st.session_state['schedule_mode'] = 'Gantt'
        st.session_state['_peims_gantt_view_migrated'] = 'v0.6.4'
    section = st.sidebar.radio("Workspace navigation", NAVIGATION,
                                format_func=lambda v: NAV_LABELS[v],
                                key="workspace_navigation", label_visibility="collapsed")
    st.sidebar.divider()
    st.sidebar.markdown('<div class="peims-sidebar-heading">PREFERENCES</div>', unsafe_allow_html=True)
    compact = st.sidebar.toggle("Compact layout", value=False, key="ui_compact")
    with st.sidebar.expander("☀️ Appearance & display", expanded=False):
        st.caption("Choose Light, Dark, or System from the app menu: ⋮ → Settings → Appearance.")
        st.caption("Theme selection is controlled by Streamlit and applies to native tables and charts.")
    st.markdown(render_css(compact), unsafe_allow_html=True)

    chosen_info = ps.loc[ps["project_id"].eq(chosen)].iloc[0]
    display_date = pd.Timestamp(chosen_info["snapshot_date"]).strftime("%d %b %Y")
    with st.sidebar.expander("Workspace information", expanded=False):
        st.caption(f"Fictional project · snapshot {display_date}")
        st.caption("Session-only edits; export backups manually. No enterprise API connection.")
    st.sidebar.caption("PEIMS · Work management 0.7 · demo mode")

    try:
        result = compute(select_project(all_data, chosen))
    except Exception as exc:
        st.error(f"The uploaded dataset has inconsistent records: {exc}. Reset the imported records in Data studio.")
        show_data_controls(base_data)
        return
    initialize_work_items(all_data, get_sample_dependencies())
    header_info = chosen_info.to_dict()
    header_info["display_date"] = display_date
    if section == "Home":
        if st.session_state.pop("peims_nav_recovered", False):
            st.info("Navigation was refreshed after an interface update. You're back on Home.")
        show_home(result, header_info, workflows)
    else:
        st.button('← Home', key='top_return_home', on_click=change_workspace,
                  args=('Home',), help='Return to your PEIMS Home page')
        st.caption(f'{chosen_info["project_name"]} · {display_date} reporting snapshot')
        if section in ('Command centre', 'Analytics studio'):
            st.markdown(render_header(header_info, result["kpi"]), unsafe_allow_html=True)
        st.markdown(render_intro(section), unsafe_allow_html=True)
        if section == "Command centre":
            show_overview(result)
        elif section == "Schedule":
            show_schedule_journey(result)
        elif section == "Cost control":
            show_cost_journey(result)
        elif section == "Procurement":
            show_procurement_journey(result)
        elif section == "Risks & actions":
            show_issues_journey(result)
        elif section == "Documents":
            show_documents_journey(all_data, workflows, chosen, chosen_info["snapshot_date"])
        elif section == "Analytics studio":
            show_analytics(result)
        elif section == "Reports":
            show_reports(result, workflows)
        elif section == "Workflows":
            show_workflow_hub(all_data, workflows, chosen, chosen_info["snapshot_date"])
        elif section == "Data studio":
            show_data_controls(base_data)
        elif section == "Spreadsheet studio":
            show_spreadsheet_studio(all_data, workflows, chosen, result)
        elif section == "Work management":
            st.caption("DEBUG ROUTER ENTERED WORK MANAGEMENT")
            show_work_management(all_data, chosen, chosen_info["snapshot_date"], get_sample_dependencies())
    st.markdown(render_safety(), unsafe_allow_html=True)
    st.markdown(render_footer(), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
