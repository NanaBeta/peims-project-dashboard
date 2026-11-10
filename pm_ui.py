"""Streamlit controls for PEIMS v0.7 Work Management (fictional, session-only)."""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
import uuid

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sheet_engine import safe_csv
from work_items import (
    TASK_COLUMNS, DEPENDENCY_COLUMNS, RULE_COLUMNS, STATUSES, PRIORITIES, KINDS,
    empty_logs, empty_rules, validate_tasks, validate_links, validate_rules,
    seeded_from_activities, new_task_id, apply_task_change, add_dependency,
    append_time, task_metrics, task_cpm, workload_weeks, calendar_month,
    export_work_backup, import_work_backup,
)


def initialize_work_items(core: dict, raw_links: pd.DataFrame) -> None:
    """One canonical project-scoped task collection across all PM views."""
    if 'pm_tasks' not in st.session_state or 'pm_dependencies' not in st.session_state:
        tasks, deps=seeded_from_activities(core['activities'],raw_links)
        st.session_state['pm_tasks']=validate_tasks(tasks,set(core['projects']['project_id']))
        st.session_state['pm_dependencies']=validate_links(deps,st.session_state['pm_tasks'])
        st.session_state['pm_time_logs']=empty_logs()
        st.session_state['pm_rules']=empty_rules()
        st.session_state['pm_capacities']={}
        st.session_state['pm_timers']={}
    # New activities added through Spreadsheet Studio are made discoverable without
    # overwriting the user's task edits or silently linking newly imported dependencies.
    old=st.session_state['pm_tasks']
    missing=core['activities'].loc[~core['activities']['activity_id'].astype(str).map(
        lambda i:f'TASK-{i}' in set(old['task_id']))]
    if not missing.empty:
        added,_=seeded_from_activities(missing,pd.DataFrame(columns=DEPENDENCY_COLUMNS))
        new=pd.concat([old,added],ignore_index=True)
        st.session_state['pm_tasks']=validate_tasks(new,set(core['projects']['project_id']))


def _save_task(task: dict, project_id: str, projects: set[str]):
    updated, automations = apply_task_change(
        st.session_state['pm_tasks'], st.session_state['pm_dependencies'],
        st.session_state['pm_time_logs'],st.session_state['pm_rules'],
        project_id,task,projects)
    st.session_state['pm_tasks']=updated
    audit=list(st.session_state.get('change_history',[]))
    audit.append({'timestamp_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                  'actor':'demo_session','project_id':project_id,
                  'register':'work_items','record_id':task['task_id'],'action':'saved'})
    for auto in automations:
        audit.append({'timestamp_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                      'actor':'demo_rule','project_id':project_id,'register':'work_rules',
                      'record_id':auto['rule_id'],'action':f"set priority {auto['value']} on {task['task_id']}"})
    st.session_state['change_history']=audit[-250:]
    st.session_state['pm_success']=f"Saved task {task['task_id']}" + ('; automation applied' if automations else '')


def _task_choice(rows: pd.DataFrame, label: str, key: str, *, allow_empty=False):
    ids=rows['task_id'].astype(str).tolist()
    options=([''] if allow_empty else [])+ids
    names=dict(zip(rows['task_id'],rows['title']))
    return st.selectbox(label,options,format_func=lambda k:'None' if not k else f'{names.get(k,k)} · {k}',key=key)


def create_task_form(tasks: pd.DataFrame, project_id: str, snapshot, project_ids: set[str]):
    with st.expander('＋ Create a task, subtask or milestone',expanded=False):
        st.caption('New work items appear instantly in Board, List, Timeline, Calendar and reporting views. '
                   'They do not silently modify the approved activity schedule or project costs.')
        with st.form(f'pm_add_task_{project_id}'):
            title=st.text_input('Task title',max_chars=180)
            a,b=st.columns(2)
            with a:
                owner=st.selectbox('Owner',sorted(set(tasks['owner'].dropna().astype(str))) or ['Project Engineer'],
                                   accept_new_options=True,help='Choose an existing project owner or type a new one')
                status=st.selectbox('Status',STATUSES)
                priority=st.selectbox('Priority',PRIORITIES,index=1)
                kind=st.selectbox('Work item type',KINDS)
            with b:
                start=st.date_input('Planned start',value=pd.Timestamp(snapshot).date())
                due=st.date_input('Due date',value=(pd.Timestamp(snapshot)+timedelta(days=7)).date())
                estimate=st.number_input('Estimated effort (hours)',min_value=0.0,max_value=100000.0,value=8.0,step=1.0)
            parent=_task_choice(tasks.loc[tasks['kind'].eq('Task')], 'Parent task (optional)',f'pm_create_parent_{project_id}',allow_empty=True)
            description=st.text_area('Description (optional)',height=78)
            submitted=st.form_submit_button('Create work item',type='primary')
        if submitted:
            try:
                if not title.strip(): raise ValueError('Enter a task title')
                if not owner.strip(): raise ValueError('Enter an owner')
                if kind=='Milestone':
                    due=start
                    estimate=0.0
                    if parent: raise ValueError('Milestones cannot be subtasks in this release')
                record=dict(zip(TASK_COLUMNS,[new_task_id(st.session_state['pm_tasks'],project_id),project_id,
                    title.strip(),description,parent,'',owner.strip(),pd.Timestamp(start),pd.Timestamp(due),
                    status,priority,kind,estimate,100.0 if status=='Done' else 0.0]))
                _save_task(record,project_id,project_ids)
                st.rerun()
            except (ValueError,KeyError,TypeError) as e:
                st.error(f'Could not create work item: {e}')


def _task_detail(tasks: pd.DataFrame, project_id: str, project_ids: set[str]):
    project=tasks.loc[tasks['project_id'].eq(project_id)]
    if project.empty: return
    task_id=_task_choice(project,'Open work item',f'pm_detail_choice_{project_id}')
    row=project.loc[project['task_id'].eq(task_id)].iloc[0]
    st.caption(f"WORK ITEM · {task_id}" + (f" · linked activity {row['linked_activity_id']}" if row['linked_activity_id'] else ''))
    with st.form(f'pm_edit_{project_id}_{task_id}'):
        a,b=st.columns(2)
        with a:
            title=st.text_input('Title',value=str(row['title']))
            owner=st.text_input('Assigned owner',value=str(row['owner']))
            status=st.selectbox('Task status',STATUSES,index=STATUSES.index(row['status']))
            priority=st.selectbox('Task priority',PRIORITIES,index=PRIORITIES.index(row['priority']))
        with b:
            start=st.date_input('Task planned start',value=pd.Timestamp(row['start_date']).date())
            due=st.date_input('Task due date',value=pd.Timestamp(row['due_date']).date())
            estimate=st.number_input('Task estimate (hours)',min_value=0.0,max_value=100000.0,
                                      value=float(row['estimate_hours']),step=1.0)
            pct=st.number_input('Reported task completion (%)',min_value=0.0,max_value=100.0,
                                 value=float(row['progress_pct']),step=5.0)
        description=st.text_area('Task description',value=str(row['description']),height=70)
        submitted=st.form_submit_button('Save task changes',type='primary')
    if submitted:
        try:
            proposed=row.to_dict()
            proposed.update(title=title,owner=owner,status=status,priority=priority,
                            start_date=pd.Timestamp(start),due_date=pd.Timestamp(due),
                            estimate_hours=estimate,progress_pct=100.0 if status=='Done' else pct,
                            description=description)
            if proposed['kind']=='Milestone':
                proposed['due_date']=pd.Timestamp(start)
                proposed['estimate_hours']=0.0
            _save_task(proposed,project_id,project_ids)
            st.rerun()
        except (ValueError,KeyError,TypeError) as e:
            st.error(f'Task update rejected: {e}')
    if row['parent_id']:
        st.caption(f"Subtask of {row['parent_id']}")
    children=project.loc[project['parent_id'].eq(task_id)]
    if not children.empty:
        st.caption(f'{len(children)} subtasks')
        st.dataframe(children[['title','status','owner','due_date','progress_pct']],hide_index=True,use_container_width=True)


def _board(tasks: pd.DataFrame, project_id: str):
    st.caption('Kanban-style board. Open a task below to change its status; interactive drag-and-drop is not yet available.')
    columns=st.columns(len(STATUSES))
    for col,status in zip(columns,STATUSES):
        with col:
            subset=tasks.loc[tasks['status'].eq(status)]
            st.markdown(f'**{status} · {len(subset)}**')
            for row in subset.head(30).itertuples(index=False):
                with st.container(border=True):
                    st.markdown(f'**{row.title}**')
                    st.caption(f'{row.owner} · {pd.Timestamp(row.due_date):%d %b} · {row.priority}')
                    if row.parent_id: st.caption('↳ Subtask')
                    if row.kind=='Milestone': st.caption('◆ Milestone')
                    if st.button('Edit →',key=f'pm_board_{project_id}_{row.task_id}',use_container_width=True):
                        # Edit panel is directly below the board, with selected ID in session state.
                        st.session_state[f'pm_detail_choice_{project_id}']=row.task_id
                        st.rerun()
            if len(subset)>30: st.caption(f'+ {len(subset)-30} more in List view')


def _timeline(tasks: pd.DataFrame,snapshot):
    st.caption('Work-item timeline; date windows are planned, not actual starts/finishes or approved revised baselines.')
    df=tasks.sort_values(['start_date','task_id']).head(70)
    fig=go.Figure()
    if df.empty: return
    labels=[f"{str(r.title)[:27]} · {r.task_id}" for r in df.itertuples(index=False)]
    lengths=(df['due_date']-df['start_date']).dt.days.clip(lower=1)+1
    durations=lengths*86400000
    details=[[str(r.title),r.owner,r.status,f'{r.progress_pct:.0f}%',str(r.task_id)] for r in df.itertuples(index=False)]
    fig.add_trace(go.Bar(x=durations.tolist(),base=df['start_date'],y=labels,orientation='h',
                         marker_color='#A8C4C5',customdata=details,
                         hovertemplate='%{customdata[0]}<br>Owner: %{customdata[1]}<br>Status: %{customdata[2]}<br>Progress: %{customdata[3]}<br>Task: %{customdata[4]}<extra></extra>',name='Planned window'))
    progress=(durations*df['progress_pct'].astype(float).div(100)).tolist()
    fig.add_trace(go.Bar(x=progress,base=df['start_date'],y=labels,orientation='h',
                         marker_color='#218B81',hoverinfo='skip',name='Reported completion'))
    milestones=df.loc[df['kind'].eq('Milestone')]
    if not milestones.empty:
        indices={r.task_id:i for i,r in enumerate(df.itertuples(index=False))}
        fig.add_trace(go.Scatter(x=milestones['due_date'],
             y=[labels[indices[t]] for t in milestones['task_id']],mode='markers',
             marker=dict(symbol='diamond',size=13,color='#B78A34'),name='Milestone'))
    fig.add_vline(x=pd.Timestamp(snapshot).timestamp()*1000,line_dash='dash',line_color='#B78A34')
    fig.update_layout(barmode='overlay',height=max(340,min(1350,130+28*len(df))),
        margin=dict(l=15,r=15,t=24,b=40),paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',legend=dict(orientation='h',y=1.07),
        xaxis=dict(type='date',gridcolor='rgba(150,165,190,.15)'),
        yaxis=dict(autorange='reversed',automargin=True,tickfont=dict(size=10)))
    st.plotly_chart(fig,use_container_width=True,key='pm_timeline_plot')
    if len(tasks)>70: st.caption('Showing the first 70 tasks by start date. Use List for the complete register.')


def _calendar(tasks: pd.DataFrame,project_id: str,snapshot):
    chosen=st.date_input('Month to view',value=pd.Timestamp(snapshot).date(),key=f'pm_calendar_{project_id}')
    grouped=calendar_month(tasks,project_id,chosen.year,chosen.month)
    st.markdown(f'### {calendar.month_name[chosen.month]} {chosen.year}')
    if grouped.empty: st.info('No work items due this month.')
    else:
        for due,rows in grouped.groupby('due_date'):
            st.markdown(f'**{pd.Timestamp(due):%a %d %b}**')
            for item in rows.itertuples(index=False):
                st.caption(f"{'◆ ' if item.kind=='Milestone' else ''}{item.title} · {item.owner} · {item.status}")
    st.caption('Calendar is based on task due dates. No drag-to-reschedule in this release.')


def _dependencies(tasks:pd.DataFrame,project_id:str):
    links=st.session_state['pm_dependencies']
    scoped=links.loc[links['project_id'].eq(project_id)]
    st.markdown('#### Finish-to-start dependencies')
    if not scoped.empty:
        st.dataframe(scoped[['predecessor_id','successor_id','lag_days']],hide_index=True,use_container_width=True)
    if len(tasks)>1:
        with st.form(f'pm_add_link_{project_id}'):
            predecessor=_task_choice(tasks,'Predecessor task',f'pm_pred_{project_id}')
            successor=_task_choice(tasks,'Successor task',f'pm_succ_{project_id}')
            lag=st.number_input('Lag (calendar days)',min_value=0,max_value=365,value=0,step=1)
            submitted=st.form_submit_button('Add dependency')
        if submitted:
            try:
                st.session_state['pm_dependencies']=add_dependency(links,st.session_state['pm_tasks'],project_id,
                                                                   predecessor,successor,int(lag))
                st.rerun()
            except ValueError as e: st.error(str(e))
    st.markdown('#### Illustrative critical path')
    try:
        model=task_cpm(st.session_state['pm_tasks'],st.session_state['pm_dependencies'],project_id)
        st.caption('Calendar-day finish-to-start CPM. This is a model, not resource leveling or an approved Primavera schedule.')
        a,b=st.columns(2)
        a.metric('Modelled finish',model['model_finish'] or '—')
        b.metric('Critical work items',len(model['critical_activity_ids']))
        if model['activities']:
            st.dataframe(pd.DataFrame(model['activities']),hide_index=True,use_container_width=True)
    except ValueError as e: st.error(f'CPM cannot be calculated: {e}')


def _workload(tasks:pd.DataFrame,project_id:str,snapshot):
    st.caption('Illustrative distribution of **remaining estimated hours** across planned calendar weeks; '
               'not actual utilization or a resource-leveled schedule.')
    owners=sorted(tasks['owner'].astype(str).unique().tolist())
    capacities=st.session_state['pm_capacities']
    if owners:
        a,b=st.columns(2)
        with a: owner=st.selectbox('Resource / owner',owners,key=f'pm_capacity_owner_{project_id}')
        with b: hours=st.number_input('Weekly capacity (hours)',min_value=0.0,max_value=168.0,
                                    value=float(capacities.get(f'{project_id}:{owner}',40.0)),step=1.0,
                                    key=f'pm_capacity_{project_id}_{owner}')
        if st.button('Save capacity',key=f'pm_save_cap_{project_id}'):
            capacities[f'{project_id}:{owner}']=float(hours)
            st.rerun()
    local_caps={owner:capacities.get(f'{project_id}:{owner}',40.0) for owner in owners}
    weeks=workload_weeks(st.session_state['pm_tasks'],project_id,snapshot,local_caps)
    if weeks.empty: st.info('Add estimated effort to outstanding tasks to calculate workloads.')
    else:
        over=weeks.loc[weeks['over_capacity']]
        if len(over): st.warning(f'{len(over)} owner-week allocations exceed the entered weekly capacity.')
        data=weeks.copy()
        data['week_start']=data['week_start'].dt.strftime('%d %b %Y')
        st.dataframe(data,hide_index=True,use_container_width=True)
        st.download_button('Export workload CSV',safe_csv(data),file_name=f'PEIMS_{project_id}_workload.csv',mime='text/csv')


def _time_and_rules(tasks:pd.DataFrame,project_id:str):
    st.markdown('#### Time records')
    st.caption('Manual time entries and a session timer; **not** authenticated payroll, billing, or continuously running background tracking.')
    task_id=_task_choice(tasks,'Work item for time entry',f'pm_log_task_{project_id}')
    with st.form(f'pm_log_form_{project_id}'):
        hours=st.number_input('Hours worked',min_value=0.01,max_value=24.0,value=1.0,step=0.25)
        note=st.text_input('Work note',max_chars=200)
        submitted=st.form_submit_button('Log time')
    if submitted:
        try:
            st.session_state['pm_time_logs']=append_time(st.session_state['pm_time_logs'],st.session_state['pm_tasks'],
                                                         project_id,task_id,float(hours),note)
            st.rerun()
        except ValueError as e: st.error(str(e))
    key=f'{project_id}:demo_session'
    active=st.session_state['pm_timers'].get(key)
    if active is None:
        if st.button('Start session timer',key=f'pm_timer_start_{project_id}'):
            st.session_state['pm_timers'][key]=(task_id,datetime.now(timezone.utc))
            st.rerun()
    else:
        running_task,started=active
        elapsed=(datetime.now(timezone.utc)-started).total_seconds()/3600
        st.info(f'Timer running for {running_task} · about {elapsed:.2f} hours (refresh to update)')
        col1,col2=st.columns(2)
        if col1.button('Stop & log time',key=f'pm_timer_stop_{project_id}'):
            duration=(datetime.now(timezone.utc)-started).total_seconds()/3600
            try:
                if duration<1/3600: raise ValueError('A timer must run at least one second')
                st.session_state['pm_time_logs']=append_time(st.session_state['pm_time_logs'],
                    st.session_state['pm_tasks'],project_id,running_task,round(duration,6),
                    'Session timer entry')
                st.session_state['pm_timers'].pop(key,None)
                st.rerun()
            except ValueError as e: st.error(str(e))
        if col2.button('Discard timer',key=f'pm_timer_discard_{project_id}'):
            st.session_state['pm_timers'].pop(key,None)
            st.rerun()
    logs=st.session_state['pm_time_logs']
    logs=logs.loc[logs['project_id'].eq(project_id)]
    if not logs.empty:
        st.dataframe(logs[['task_id','logged_on','hours','note']],hide_index=True,use_container_width=True)
        st.metric('Logged project hours',f"{logs['hours'].sum():.2f} h")
    st.divider()
    st.markdown('#### Simple no-code rules')
    st.caption('A rule can set the priority when a task changes status. Applied only on a saved status transition, '
               'within this session. No external messages, approvals or notifications are sent.')
    rules=st.session_state['pm_rules']
    project_rules=rules.loc[rules['project_id'].eq(project_id)]
    if not project_rules.empty:
        st.dataframe(project_rules[['when_status','set_priority','enabled']],hide_index=True,use_container_width=True)
    with st.form(f'pm_new_rule_{project_id}'):
        a,b=st.columns(2)
        with a: trigger=st.selectbox('When task status becomes',STATUSES,index=3)
        with b: effect=st.selectbox('Then set task priority to',PRIORITIES,index=2)
        enabled=st.checkbox('Enable rule',value=True)
        add=st.form_submit_button('Add automation rule')
    if add:
        new=pd.DataFrame([{'rule_id':uuid.uuid4().hex,'project_id':project_id,
                           'when_status':trigger,'set_priority':effect,'enabled':bool(enabled)}])
        try:
            st.session_state['pm_rules']=validate_rules(pd.concat([rules,new],ignore_index=True),
                                                  set(st.session_state['current_core']['projects']['project_id']))
            st.rerun()
        except ValueError as e: st.error(str(e))
    if not project_rules.empty:
        ids=project_rules['rule_id'].tolist()
        choice=st.selectbox('Manage rule',ids,format_func=lambda x: f"{project_rules.loc[project_rules.rule_id.eq(x),'when_status'].iloc[0]} → {project_rules.loc[project_rules.rule_id.eq(x),'set_priority'].iloc[0]}")
        if st.button('Delete selected rule',key=f'pm_remove_rule_{project_id}'):
            st.session_state['pm_rules']=rules.loc[~rules['rule_id'].eq(choice)].copy().reset_index(drop=True)
            st.rerun()


def show_work_management(core:dict, project_id:str, snapshot, raw_dependencies:pd.DataFrame):
    import sys
    print('DEBUG_PM_HANDLER_FUNCTION_STARTED',project_id,file=sys.stderr,flush=True)
    initialize_work_items(core,raw_dependencies)
    print('DEBUG_PM_INITIALIZATION_DONE',file=sys.stderr,flush=True)
    all_tasks=st.session_state['pm_tasks']
    tasks=all_tasks.loc[all_tasks['project_id'].eq(project_id)].copy()
    logs=st.session_state['pm_time_logs']
    metrics=task_metrics(all_tasks,logs,project_id,snapshot)
    st.caption('Task management demo · project-scoped · session-only · separate from approved baseline activities')
    if st.session_state.pop('pm_success',None):
        st.success('Work item saved in this session.')
    col=st.columns(4)
    for c,(label,value) in zip(col,[('Work items',metrics['total']),('Open',metrics['open']),
                                   ('Overdue at snapshot',metrics['overdue']),('Milestones',metrics['milestones'])]):
        c.metric(label,value)
    create_task_form(tasks,project_id,snapshot,set(core['projects']['project_id']))
    tabs=['Board','List','Timeline','Calendar','Dependencies & CPM','Workload','Time & rules']
    view=st.radio('Work view',tabs,horizontal=True,key=f'pm_view_{project_id}')
    if view in ('Board','List','Timeline','Calendar'):
        left,right=st.columns(2)
        with left:
            owner_filter=st.selectbox('Filter owner',['All owners']+sorted(tasks['owner'].unique().tolist()),
                                      key=f'pm_owner_filter_{project_id}')
        with right:
            status_filter=st.selectbox('Filter status',['All statuses']+list(STATUSES),
                                       key=f'pm_status_filter_{project_id}')
        if owner_filter!='All owners':
            tasks=tasks.loc[tasks['owner'].eq(owner_filter)]
        if status_filter!='All statuses':
            tasks=tasks.loc[tasks['status'].eq(status_filter)]
        st.caption(f'{len(tasks)} matching work items')
    if view=='Board': _board(tasks,project_id)
    elif view=='List':
        st.markdown('#### Task register')
        st.dataframe(tasks[['task_id','title','parent_id','owner','status','priority','kind','start_date','due_date',
                            'estimate_hours','progress_pct']],hide_index=True,use_container_width=True)
        st.download_button('Export work items CSV',safe_csv(tasks),
                           file_name=f'PEIMS_{project_id}_tasks.csv',mime='text/csv')
    elif view=='Timeline': _timeline(tasks,snapshot)
    elif view=='Calendar': _calendar(tasks,project_id,snapshot)
    elif view=='Dependencies & CPM': _dependencies(tasks,project_id)
    elif view=='Workload': _workload(tasks,project_id,snapshot)
    elif view=='Time & rules': _time_and_rules(tasks,project_id)
    if view in ('Board','List','Timeline','Calendar'):
        st.divider()
        st.markdown('#### Task details & updates')
        _task_detail(st.session_state['pm_tasks'],project_id,set(core['projects']['project_id']))
    with st.expander('Backup / restore project work records',expanded=False):
        st.caption('Export tasks, dependencies, time entries, rules and resource capacities for this project. '
                   'Restoring replaces this project’s task data only and never changes approved activities.')
        backup=export_work_backup(st.session_state['pm_tasks'],st.session_state['pm_dependencies'],
                                  st.session_state['pm_time_logs'],st.session_state['pm_rules'],
                                  project_id,st.session_state['pm_capacities'])
        st.download_button('Download project work backup',backup,
                           file_name=f'PEIMS_{project_id}_work_backup.zip',mime='application/zip')
        upload=st.file_uploader('Restore project work backup (.zip)',type=['zip'],
                                key=f'pm_work_backup_{project_id}')
        confirmed=st.checkbox('I understand this replaces work-management entries for the selected project',
                              key=f'pm_restore_agree_{project_id}')
        if st.button('Validate & restore project work',disabled=upload is None or not confirmed,
                     key=f'pm_restore_backup_{project_id}'):
            try:
                updated=import_work_backup(upload.getvalue(),project_id,st.session_state['pm_tasks'],
                    st.session_state['pm_dependencies'],st.session_state['pm_time_logs'],
                    st.session_state['pm_rules'],st.session_state['pm_capacities'],
                    set(core['projects']['project_id']))
                for k,v in zip(('pm_tasks','pm_dependencies','pm_time_logs','pm_rules','pm_capacities'),updated):
                    st.session_state[k]=v
                st.session_state['pm_timers'].pop(f'{project_id}:demo_session',None)
                st.rerun()
            except (ValueError,TypeError,KeyError) as e:
                st.error(f'Backup was not restored: {e}')
    st.caption('Existing baseline Gantt, costs and activity progress remain the authoritative project controls. '
               'The new work-item timeline does not change those records automatically.')
