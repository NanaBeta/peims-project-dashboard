"""PEIMS work-management domain: one project-scoped set of tasks for every view.

Demo-only in-memory records. Task due dates, status, and logged hours are not
approved project schedule actuals, payroll timesheets, or contractual commitments.
No notifications, external integrations, or background timers are performed here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from collections import defaultdict
import re
import uuid
import pandas as pd

from project_controls import critical_path

TASK_COLUMNS = (
    'task_id', 'project_id', 'title', 'description', 'parent_id', 'linked_activity_id',
    'owner', 'start_date', 'due_date', 'status', 'priority', 'kind',
    'estimate_hours', 'progress_pct',
)
DEPENDENCY_COLUMNS = ('project_id', 'predecessor_id', 'successor_id', 'lag_days')
TIME_COLUMNS = ('log_id', 'project_id', 'task_id', 'actor', 'logged_on', 'hours', 'note')
RULE_COLUMNS = ('rule_id', 'project_id', 'when_status', 'set_priority', 'enabled')
STATUSES = ('To do', 'In progress', 'In review', 'Blocked', 'Done')
PRIORITIES = ('Low', 'Medium', 'High', 'Critical')
KINDS = ('Task', 'Milestone')
MAX_TASKS = 2500
MAX_LOGS = 10000
MAX_DEPS = 5000


def empty_tasks() -> pd.DataFrame:
    return pd.DataFrame(columns=TASK_COLUMNS)


def empty_links() -> pd.DataFrame:
    return pd.DataFrame(columns=DEPENDENCY_COLUMNS)


def empty_logs() -> pd.DataFrame:
    return pd.DataFrame(columns=TIME_COLUMNS)


def empty_rules() -> pd.DataFrame:
    return pd.DataFrame(columns=RULE_COLUMNS)


def _clean_identifier(value: str, field: str) -> str:
    value = str(value).strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise ValueError(f'{field} needs 1–64 letters, numbers, hyphens or underscores')
    return value


def validate_tasks(frame: pd.DataFrame, project_ids: set[str]) -> pd.DataFrame:
    if not set(TASK_COLUMNS).issubset(frame.columns):
        raise ValueError('Task record fields are missing')
    if len(frame) > MAX_TASKS:
        raise ValueError('Too many tasks for this demonstration workspace')
    df = frame[list(TASK_COLUMNS)].copy().reset_index(drop=True)
    for col in ('task_id', 'project_id', 'title', 'description', 'parent_id',
                'linked_activity_id', 'owner', 'status', 'priority', 'kind'):
        df[col] = df[col].fillna('').astype(str).str.strip()
        if df[col].str.len().gt(1000).any():
            raise ValueError(f'{col} is too long')
    if not df['task_id'].map(lambda v: bool(re.fullmatch(r'[A-Za-z0-9_-]{1,64}', v))).all():
        raise ValueError('Invalid task ID')
    if df['task_id'].duplicated().any():
        raise ValueError('Task IDs must be unique across projects')
    if not df['project_id'].isin(project_ids).all():
        raise ValueError('Task belongs to an unknown project')
    if df['title'].eq('').any() or df['owner'].eq('').any():
        raise ValueError('Task title and owner are required')
    if not df['status'].isin(STATUSES).all() or not df['priority'].isin(PRIORITIES).all():
        raise ValueError('Unsupported task status or priority')
    if not df['kind'].isin(KINDS).all():
        raise ValueError('Unsupported work item type')
    for col in ('start_date', 'due_date'):
        df[col] = pd.to_datetime(df[col], errors='coerce').dt.normalize()
        if df[col].isna().any():
            raise ValueError(f'{col} must contain a valid date')
    if (df['due_date'] < df['start_date']).any():
        raise ValueError('Due date cannot precede start date')
    df['estimate_hours'] = pd.to_numeric(df['estimate_hours'], errors='coerce')
    df['progress_pct'] = pd.to_numeric(df['progress_pct'], errors='coerce')
    if (df[['estimate_hours', 'progress_pct']].isna().any().any() or
        (df['estimate_hours'] < 0).any() or (df['estimate_hours'] > 100000).any() or
        not df['progress_pct'].between(0,100).all()):
        raise ValueError('Estimate and completion percentages are invalid')
    if (df.loc[df['kind'].eq('Milestone'), 'start_date'] !=
        df.loc[df['kind'].eq('Milestone'), 'due_date']).any():
        raise ValueError('A milestone must have the same start and due date')
    if (df.loc[df['kind'].eq('Milestone'), 'estimate_hours'] != 0).any():
        raise ValueError('Milestones have zero estimated hours')
    if df.loc[df['status'].eq('Done'), 'progress_pct'].ne(100).any():
        raise ValueError('Completed tasks must have 100% progress')
    records = df.set_index('task_id')
    for r in df.itertuples(index=False):
        if r.parent_id:
            if r.parent_id == r.task_id or r.parent_id not in records.index:
                raise ValueError('Unknown or self-referencing parent task')
            if records.at[r.parent_id, 'project_id'] != r.project_id:
                raise ValueError('A subtask cannot reference another project')
        if r.kind == 'Milestone' and r.parent_id:
            raise ValueError('Milestones cannot be subtasks in this release')
    for row in df.itertuples(index=False):
        seen = {row.task_id}
        parent = row.parent_id
        while parent:
            if parent in seen:
                raise ValueError('Subtask hierarchy contains a cycle')
            seen.add(parent)
            parent = records.at[parent, 'parent_id']
    return df


def validate_links(frame: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    if not set(DEPENDENCY_COLUMNS).issubset(frame.columns):
        raise ValueError('Dependency columns are missing')
    if len(frame) > MAX_DEPS:
        raise ValueError('Too many task links')
    df = frame[list(DEPENDENCY_COLUMNS)].copy().reset_index(drop=True)
    if df.empty:
        return df
    ids = tasks.set_index('task_id')['project_id'].to_dict()
    for row in df.itertuples(index=False):
        if (row.predecessor_id not in ids or row.successor_id not in ids or
            ids[row.predecessor_id] != row.project_id or ids[row.successor_id] != row.project_id):
            raise ValueError('Dependency cannot reference another project or an unknown task')
        if row.predecessor_id == row.successor_id:
            raise ValueError('Self-dependent tasks are not allowed')
    if df.duplicated(['project_id','predecessor_id','successor_id']).any():
        raise ValueError('Duplicate dependency')
    lag = pd.to_numeric(df['lag_days'], errors='coerce')
    if lag.isna().any() or (lag < 0).any() or (lag != lag.astype(int)).any():
        raise ValueError('Only nonnegative whole-day dependency lags are supported')
    df['lag_days'] = lag.astype(int)
    for pid in tasks['project_id'].unique():
        project_tasks = tasks.loc[tasks['project_id'].eq(pid)]
        project_links = df.loc[df['project_id'].eq(pid)]
        if not project_tasks.empty:
            critical_path(project_tasks.rename(columns={'task_id':'activity_id','due_date':'finish_date'}), project_links)
    return df


def task_cpm(tasks: pd.DataFrame, links: pd.DataFrame, project_id: str) -> dict:
    scoped = tasks.loc[tasks['project_id'].eq(project_id)]
    if scoped.empty:
        return {'activities': [], 'critical_activity_ids':[], 'model_finish':None,
                'assumptions':'No tasks'}
    dependencies = links.loc[links['project_id'].eq(project_id)]
    return critical_path(scoped.rename(columns={'task_id':'activity_id','due_date':'finish_date'}), dependencies)


def validate_logs(frame: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    if not set(TIME_COLUMNS).issubset(frame.columns):
        raise ValueError('Time record fields are missing')
    if len(frame) > MAX_LOGS:
        raise ValueError('Too many time records')
    df = frame[list(TIME_COLUMNS)].copy().reset_index(drop=True)
    if df.empty:
        return df
    if df['log_id'].astype(str).duplicated().any():
        raise ValueError('Duplicate time log ID')
    ids = tasks.set_index('task_id')['project_id'].to_dict()
    for row in df.itertuples(index=False):
        if ids.get(row.task_id) != row.project_id:
            raise ValueError('Time entry cannot cross project boundaries')
        if not str(row.actor).strip():
            raise ValueError('Time entry requires an actor')
    df['logged_on'] = pd.to_datetime(df['logged_on'], errors='coerce').dt.normalize()
    df['hours'] = pd.to_numeric(df['hours'], errors='coerce')
    if df['logged_on'].isna().any() or df['hours'].isna().any() or not ((df['hours'] > 0) & (df['hours'] <= 24)).all():
        raise ValueError('Time entries must have a date and positive hours up to 24')
    return df


def validate_rules(frame: pd.DataFrame, projects: set[str]) -> pd.DataFrame:
    if not set(RULE_COLUMNS).issubset(frame.columns):
        raise ValueError('Rule fields are missing')
    df = frame[list(RULE_COLUMNS)].copy().reset_index(drop=True)
    if df.empty:
        return df
    if df['rule_id'].duplicated().any() or not df['project_id'].isin(projects).all():
        raise ValueError('Duplicate rule or invalid project')
    if not df['when_status'].isin(STATUSES).all() or not df['set_priority'].isin(PRIORITIES).all():
        raise ValueError('Invalid automation trigger or action')
    if not df['enabled'].map(lambda x: isinstance(x, bool)).all():
        raise ValueError('Automation enabled must be boolean')
    return df


def seeded_from_activities(activities: pd.DataFrame, source_links: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    """One work item per baseline activity. Project Gantt is still source-of-truth."""
    tasks = []
    for row in activities.itertuples(index=False):
        progress = float(row.actual_pct)
        tasks.append({
            'task_id': f'TASK-{row.activity_id}', 'project_id': row.project_id,
            'title': row.activity, 'description': 'Linked to the original project activity',
            'parent_id':'', 'linked_activity_id': row.activity_id, 'owner':row.owner,
            'start_date':row.start_date, 'due_date':row.finish_date,
            'status':'Done' if progress>=100 else ('In progress' if progress>0 else 'To do'),
            'priority':'Medium', 'kind':'Task', 'estimate_hours':0.0,
            'progress_pct':progress,
        })
    df = pd.DataFrame(tasks, columns=TASK_COLUMNS)
    mapping = set(df['task_id'])
    links = []
    for row in source_links.itertuples(index=False):
        pred, succ = f'TASK-{row.predecessor_id}', f'TASK-{row.successor_id}'
        if pred in mapping and succ in mapping:
            links.append({'project_id':row.project_id,'predecessor_id':pred,
                          'successor_id':succ,'lag_days':int(row.lag_days)})
    return df, pd.DataFrame(links,columns=DEPENDENCY_COLUMNS)


def new_task_id(tasks: pd.DataFrame, project_id: str) -> str:
    used=set(tasks['task_id'].astype(str))
    for n in range(1,100000):
        candidate=f'{project_id}-TASK-{n:04d}'
        if candidate not in used:
            return candidate
    raise ValueError('Task ID range exhausted')


def apply_task_change(tasks: pd.DataFrame, links: pd.DataFrame, logs: pd.DataFrame,
                      rules: pd.DataFrame, project_id: str, row: dict,
                      projects: set[str]) -> tuple[pd.DataFrame,list[dict]]:
    """Transactional create/update; never alter tasks outside the chosen project."""
    if project_id not in projects:
        raise ValueError('Unknown project')
    proposed = dict(row)
    proposed['task_id']=_clean_identifier(proposed['task_id'],'Task ID')
    proposed['project_id']=project_id
    current = tasks.copy()
    mask = current['task_id'].astype(str).eq(proposed['task_id'])
    if mask.any():
        if str(current.loc[mask,'project_id'].iloc[0]) != project_id:
            raise ValueError('Cannot update another project’s task')
        for col in TASK_COLUMNS:
            if col in ('task_id', 'project_id'):
                continue
            current.loc[mask,col] = proposed[col]
        action='updated'
        old_status=str(tasks.loc[mask,'status'].iloc[0])
    else:
        current=pd.concat([current,pd.DataFrame([proposed])],ignore_index=True)
        action='created'
        old_status=''
    transitions=[]
    status=proposed['status']
    if old_status!=status:
        for rule in rules.loc[rules['project_id'].eq(project_id)].to_dict('records'):
            if rule['enabled'] and rule['when_status']==status:
                current.loc[current['task_id'].eq(proposed['task_id']),'priority']=rule['set_priority']
                transitions.append({'rule_id':rule['rule_id'],'action':'set_priority','value':rule['set_priority']})
    if status=='Done':
        current.loc[current['task_id'].eq(proposed['task_id']),'progress_pct']=100.0
    validated=validate_tasks(current,projects)
    validate_links(links,validated)
    validate_logs(logs,validated)
    return validated, transitions


def add_dependency(links: pd.DataFrame, tasks: pd.DataFrame, project_id: str,
                   predecessor: str, successor: str, lag_days: int=0) -> pd.DataFrame:
    new=pd.DataFrame([{'project_id':project_id,'predecessor_id':predecessor,
                       'successor_id':successor,'lag_days':lag_days}])
    return validate_links(pd.concat([links,new],ignore_index=True),tasks)


def append_time(logs: pd.DataFrame, tasks: pd.DataFrame, project_id: str,
                task_id: str, hours: float, note: str, *, actor: str='demo_session', logged_on=None
                ) -> pd.DataFrame:
    record={'log_id':uuid.uuid4().hex,'project_id':project_id,'task_id':task_id,
            'actor':actor,'logged_on': pd.Timestamp(logged_on or datetime.now(timezone.utc)).normalize(),
            'hours':hours,'note':str(note)[:1000]}
    return validate_logs(pd.concat([logs,pd.DataFrame([record])],ignore_index=True),tasks)


def task_metrics(tasks: pd.DataFrame, logs: pd.DataFrame, project_id: str, snapshot) -> dict:
    scoped=tasks.loc[tasks['project_id'].eq(project_id)]
    dated=pd.Timestamp(snapshot).normalize()
    done=scoped['status'].eq('Done')
    logged=logs.loc[logs['project_id'].eq(project_id)] if not logs.empty else logs
    return {'total':len(scoped),'done':int(done.sum()),
            'open':int((~done).sum()),
            'overdue':int(((~done)&(scoped['due_date']<dated)).sum()),
            'blocked':int(scoped['status'].eq('Blocked').sum()),
            'milestones':int(scoped['kind'].eq('Milestone').sum()),
            'completion':round(float(scoped['progress_pct'].mean()),1) if len(scoped) else 0.0,
            'estimated_hours':float(scoped['estimate_hours'].sum()),
            'logged_hours':float(logged['hours'].sum()) if len(logged) else 0.0}


def workload_weeks(tasks: pd.DataFrame, project_id: str, snapshot, capacities: dict[str,float] | None=None
                  ) -> pd.DataFrame:
    """Illustrative remaining effort spread evenly over remaining planned calendar weeks.

    Work already overdue is treated as backlog in the snapshot week. This is
    NOT resource leveling, a timesheet or a utilization measurement.
    """
    frame=tasks.loc[tasks['project_id'].eq(project_id) & tasks['status'].ne('Done')]
    snap=pd.Timestamp(snapshot).normalize()
    totals: dict[tuple[str,pd.Timestamp],float]=defaultdict(float)
    for r in frame.itertuples(index=False):
        remaining=max(0.0,float(r.estimate_hours)*(1-float(r.progress_pct)/100))
        if not remaining: continue
        begin=max(pd.Timestamp(r.start_date),snap)
        finish=max(pd.Timestamp(r.due_date),begin)
        # Use Mondays; cap horizon to preserve interactive responsiveness.
        start_week=begin-timedelta(days=begin.weekday())
        end_week=finish-timedelta(days=finish.weekday())
        count=min(105,int((end_week-start_week).days//7)+1)
        for w in range(count):
            totals[(r.owner,start_week+timedelta(days=w*7))]+=remaining/count
    records=[]
    for (owner,week),hrs in sorted(totals.items(),key=lambda x:(x[0][1],x[0][0])):
        available=float((capacities or {}).get(owner,40.0))
        records.append({'owner':owner,'week_start':week,'planned_hours':round(hrs,2),
                        'weekly_capacity':available,'over_capacity':hrs>available})
    return pd.DataFrame(records,columns=['owner','week_start','planned_hours','weekly_capacity','over_capacity'])


def calendar_month(tasks: pd.DataFrame, project_id: str, year: int, month: int) -> pd.DataFrame:
    frame=tasks.loc[tasks['project_id'].eq(project_id)].copy()
    frame['due_date']=pd.to_datetime(frame['due_date'])
    return frame.loc[(frame['due_date'].dt.year==year)&(frame['due_date'].dt.month==month)].sort_values(['due_date','priority'])


def export_work_backup(tasks: pd.DataFrame, links: pd.DataFrame, logs: pd.DataFrame,
                       rules: pd.DataFrame, project_id: str, capacities: dict) -> bytes:
    """Portable, project-only archive. No shared database or automatic sync."""
    from io import BytesIO
    from zipfile import ZipFile, ZIP_DEFLATED
    import json

    payload={'format':'peims-work-v1','project_id':project_id}
    for name,frame in [('tasks',tasks),('dependencies',links),('time_logs',logs),('rules',rules)]:
        sub=frame.loc[frame['project_id'].eq(project_id)].copy()
        for col in sub.select_dtypes(include=['datetime64[ns]','datetimetz']).columns:
            sub[col]=sub[col].dt.strftime('%Y-%m-%d')
        payload[name]=sub.where(pd.notnull(sub),None).to_dict(orient='records')
    payload['capacities']={k:float(v) for k,v in capacities.items() if k.startswith(project_id+':')}
    output=BytesIO()
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        archive.writestr('peims_work.json',json.dumps(payload,ensure_ascii=False,allow_nan=False))
    return output.getvalue()


def import_work_backup(data: bytes, project_id: str, tasks: pd.DataFrame,
                       links: pd.DataFrame, logs: pd.DataFrame, rules: pd.DataFrame,
                       capacities: dict, project_ids: set[str]):
    """Validate all loaded data atomically before replacing only one project."""
    import json
    from io import BytesIO
    from zipfile import ZipFile, BadZipFile
    if not data or len(data)>4*1024*1024:
        raise ValueError('Work-management backup exceeds size limit')
    try:
        with ZipFile(BytesIO(data)) as archive:
            info=archive.infolist()
            if len(info)!=1 or info[0].filename!='peims_work.json' or info[0].file_size>15*1024*1024:
                raise ValueError('Invalid work-management archive contents')
            payload=json.loads(archive.read('peims_work.json'))
    except (BadZipFile, UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
        raise ValueError('Invalid work-management backup') from exc
    if payload.get('format')!='peims-work-v1' or payload.get('project_id')!=project_id:
        raise ValueError('Backup does not match the selected project')
    if project_id not in project_ids:
        raise ValueError('Unknown project')
    frames={}
    for name,old,columns in [('tasks',tasks,TASK_COLUMNS),('dependencies',links,DEPENDENCY_COLUMNS),
                             ('time_logs',logs,TIME_COLUMNS),('rules',rules,RULE_COLUMNS)]:
        content=payload.get(name)
        if not isinstance(content,list):
            raise ValueError(f'Missing or invalid backup register: {name}')
        if len(content)>{'tasks':MAX_TASKS,'dependencies':MAX_DEPS,'time_logs':MAX_LOGS,'rules':500}[name]:
            raise ValueError('Backup contains too many entries')
        if any(not isinstance(row,dict) or set(row)!=set(columns) or row.get('project_id')!=project_id
               for row in content):
            raise ValueError(f'Backup {name} contains invalid fields or other-project data')
        combined=pd.concat([old.loc[~old['project_id'].eq(project_id)],
                            pd.DataFrame(content,columns=columns)],ignore_index=True)
        frames[name]=combined
    new_tasks=validate_tasks(frames['tasks'],project_ids)
    new_deps=validate_links(frames['dependencies'],new_tasks)
    new_logs=validate_logs(frames['time_logs'],new_tasks)
    # JSON represents boolean true/false as Python booleans.
    new_rules=validate_rules(frames['rules'],project_ids)
    directory=payload.get('capacities',{})
    if not isinstance(directory,dict) or len(directory)>500:
        raise ValueError('Invalid capacity backup')
    new_caps={k:v for k,v in capacities.items() if not k.startswith(project_id+':')}
    for k,v in directory.items():
        if not isinstance(k,str) or not k.startswith(project_id+':') or not isinstance(v,(int,float)) or not 0<=v<=168:
            raise ValueError('Invalid capacity or cross-project access in backup')
        new_caps[k]=float(v)
    return new_tasks,new_deps,new_logs,new_rules,new_caps
