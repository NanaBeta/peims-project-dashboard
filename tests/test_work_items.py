"""PEIMS v0.7 project-scoped tasks, dependencies, milestones and work logs."""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import pytest

from analytics import DATASET_COLUMNS, validated_frame
from project_controls import critical_path
from work_items import (
    TASK_COLUMNS, DEPENDENCY_COLUMNS, RULE_COLUMNS,STATUSES,
    seeded_from_activities, validate_tasks, validate_links, validate_logs,
    empty_logs, empty_rules, apply_task_change, add_dependency, append_time,
    task_metrics,task_cpm,workload_weeks,calendar_month,new_task_id,validate_rules,
)

ROOT=Path(__file__).resolve().parents[1]


def demo():
    activities=validated_frame('activities',pd.read_csv(ROOT/'data/activities.csv'))
    deps=pd.read_csv(ROOT/'data/dependencies.csv')
    tasks,links=seeded_from_activities(activities,deps)
    ids=set(activities.project_id.unique())
    return validate_tasks(tasks,ids),validate_links(links,tasks),ids


def test_seeded_activity_links_and_project_isolation():
    tasks,links,ids=demo()
    assert len(tasks)==len(pd.read_csv(ROOT/'data/activities.csv'))
    assert set(tasks.linked_activity_id) == set(pd.read_csv(ROOT/'data/activities.csv').activity_id)
    assert links.shape[0]>0
    assert len(ids)==2
    assert all(tasks.loc[tasks.task_id.eq(r.predecessor_id),'project_id'].iat[0]==r.project_id for r in links.itertuples(index=False))
    assert new_task_id(tasks,'UGV-001').startswith('UGV-001-TASK-')


def test_task_creation_and_subtask_updates_project_scoped():
    tasks,links,ids=demo()
    other=tasks.loc[tasks.project_id.eq('DWP-002')].copy().reset_index(drop=True)
    row={'task_id':'UGV-001-TASK-3001','project_id':'DWP-002','title':'Inspect MCC interlocks',
         'description':'Fictional test','parent_id':'TASK-V04','linked_activity_id':'',
         'owner':'Electrical Engineer','start_date':'2026-11-11','due_date':'2026-11-14',
         'status':'To do','priority':'High','kind':'Task','estimate_hours':12,'progress_pct':0}
    result,changes=apply_task_change(tasks,links,empty_logs(),empty_rules(),'UGV-001',row,ids)
    assert not changes
    assert len(result)==len(tasks)+1
    assert result.loc[result.task_id.eq(row['task_id']),'project_id'].iat[0]=='UGV-001'
    pd.testing.assert_frame_equal(result.loc[result.project_id.eq('DWP-002')].reset_index(drop=True),other)
    row['status']='Done';row['progress_pct']=20
    revised,_=apply_task_change(result,links,empty_logs(),empty_rules(),'UGV-001',row,ids)
    assert revised.loc[revised.task_id.eq(row['task_id']),'progress_pct'].iat[0]==100


def test_reject_cross_project_update_and_parent():
    tasks,links,ids=demo()
    stolen=tasks.loc[tasks.project_id.eq('DWP-002')].iloc[0].to_dict()
    with pytest.raises(ValueError,match='another project'):
        apply_task_change(tasks,links,empty_logs(),empty_rules(),'UGV-001',stolen,ids)
    new=tasks.iloc[0].to_dict();new.update(task_id='TEST-100',project_id='UGV-001',parent_id=stolen['task_id'])
    with pytest.raises(ValueError,match='another project'):
        apply_task_change(tasks,links,empty_logs(),empty_rules(),'UGV-001',new,ids)


def test_reject_subtask_cycles_and_invalid_milestone():
    tasks,links,ids=demo()
    first=tasks.iloc[0].task_id
    second=tasks.iloc[1].task_id
    changed=tasks.copy()
    changed.loc[changed.task_id.eq(first),'parent_id']=second
    changed.loc[changed.task_id.eq(second),'parent_id']=first
    with pytest.raises(ValueError,match='cycle'):
        validate_tasks(changed,ids)
    milestone=tasks.iloc[0].to_dict()
    milestone.update(task_id='MILESTONE-1',kind='Milestone',estimate_hours=8, due_date=milestone['start_date'])
    with pytest.raises(ValueError,match='zero'):
        validate_tasks(pd.concat([tasks,pd.DataFrame([milestone])],ignore_index=True),ids)


def test_dependency_cycle_unknown_and_duplicate_rejected():
    tasks,links,ids=demo()
    subset=tasks.loc[tasks.project_id.eq('UGV-001')]
    # Build a cycle with a fresh isolated dependency network to make topology exact.
    short=subset.iloc[:2].copy()
    empty=pd.DataFrame(columns=DEPENDENCY_COLUMNS)
    d1=add_dependency(empty,short,'UGV-001',short.iloc[0].task_id,short.iloc[1].task_id)
    with pytest.raises(ValueError,match='cycle'):
        add_dependency(d1,short,'UGV-001',short.iloc[1].task_id,short.iloc[0].task_id)
    with pytest.raises(ValueError,match='Duplicate'):
        add_dependency(d1,short,'UGV-001',short.iloc[0].task_id,short.iloc[1].task_id)
    foreign=tasks.loc[tasks.project_id.eq('DWP-002')].iloc[0].task_id
    with pytest.raises(ValueError,match='another project'):
        add_dependency(empty,tasks,'UGV-001',short.iloc[0].task_id,foreign)


def test_cpm_explains_calendar_day_assumptions():
    tasks,links,_=demo()
    m=task_cpm(tasks,links,'UGV-001')
    assert len(m['activities'])>0
    assert m['critical_activity_ids']
    assert 'calendar-day' in m['assumptions']


def test_milestone_and_calendar_month_are_consistent():
    tasks,links,ids=demo()
    record=tasks.iloc[0].to_dict()
    record.update(task_id='MILESTONE-002',kind='Milestone',status='To do',
                  start_date='2026-11-15',due_date='2026-11-15',estimate_hours=0,progress_pct=0)
    updated,_=apply_task_change(tasks,links,empty_logs(),empty_rules(),'UGV-001',record,ids)
    found=calendar_month(updated,'UGV-001',2026,11)
    assert record['task_id'] in set(found.task_id)
    assert not set(calendar_month(updated,'DWP-002',2026,11).task_id).intersection({record['task_id']})


def test_time_records_reject_cross_project_and_overlong_entries():
    tasks,_,_=demo()
    task_id=tasks.loc[tasks.project_id.eq('UGV-001')].iloc[0].task_id
    logs=append_time(empty_logs(),tasks,'UGV-001',task_id,3.5,'Test installation')
    assert len(logs)==1
    with pytest.raises(ValueError,match='cross project'):
        append_time(empty_logs(),tasks,'DWP-002',task_id,1,'Cross project')
    with pytest.raises(ValueError,match='positive hours'):
        append_time(empty_logs(),tasks,'UGV-001',task_id,26,'Excess')
    assert task_metrics(tasks,logs,'UGV-001','2026-11-09')['logged_hours']==3.5


def test_workload_respects_remaining_effort_and_capacity():
    tasks,_,ids=demo()
    row=tasks.loc[tasks.project_id.eq('UGV-001') & tasks.status.ne('Done')].iloc[0].to_dict()
    row.update(task_id='WORKLOAD-NEW',estimate_hours=120,progress_pct=0,
               start_date='2026-11-09',due_date='2026-11-15',owner='New Test Engineer')
    tasks=validate_tasks(pd.concat([tasks,pd.DataFrame([row])],ignore_index=True),ids)
    load=workload_weeks(tasks,'UGV-001','2026-11-09',{'New Test Engineer':35})
    match=load.loc[load.owner.eq('New Test Engineer')]
    assert len(match)==1 and bool(match.iloc[0].over_capacity)
    assert round(match.planned_hours.sum(),2)==120
    assert 'New Test Engineer' not in set(workload_weeks(tasks,'DWP-002','2026-11-09').owner)


def test_rules_only_fire_on_status_change_with_same_project():
    tasks,links,ids=demo()
    rule=pd.DataFrame([{'rule_id':'r1','project_id':'UGV-001','when_status':'Blocked',
                        'set_priority':'Critical','enabled':True}],columns=RULE_COLUMNS)
    rule=validate_rules(rule,ids)
    row=tasks.loc[tasks.project_id.eq('UGV-001') & tasks.status.ne('Done')].iloc[0].to_dict()
    row['status']='Blocked'
    updated,changes=apply_task_change(tasks,links,empty_logs(),rule,'UGV-001',row,ids)
    assert len(changes)==1 and changes[0]['rule_id']=='r1'
    assert updated.loc[updated.task_id.eq(row['task_id']),'priority'].iat[0]=='Critical'
    _,changes=apply_task_change(updated,links,empty_logs(),rule,'UGV-001',row,ids)
    assert not changes
    dwp=tasks.loc[tasks.project_id.eq('DWP-002') & tasks.status.ne('Done')].iloc[0].to_dict()
    dwp['status']='Blocked'
    result,changes=apply_task_change(tasks,links,empty_logs(),rule,'DWP-002',dwp,ids)
    assert not changes
    assert result.loc[result.task_id.eq(dwp['task_id']),'priority'].iat[0]==dwp['priority']


def test_work_archive_roundtrip_preserves_other_project_and_blocks_foreign_backup():
    from work_items import export_work_backup,import_work_backup
    tasks,links,ids=demo()
    logs=empty_logs();rules=empty_rules()
    cap={'UGV-001:Electrical Engineer':24,'DWP-002:Design Team':30}
    raw=export_work_backup(tasks,links,logs,rules,'UGV-001',cap)
    restored=import_work_backup(raw,'UGV-001',tasks,links,logs,rules,cap,ids)
    assert restored[0].shape==tasks.shape
    assert restored[4]==cap
    with pytest.raises(ValueError,match='selected project'):
        import_work_backup(raw,'DWP-002',tasks,links,logs,rules,cap,ids)


def test_work_archive_rejects_cross_project_rows_inside_selected_project():
    from work_items import export_work_backup, import_work_backup
    from io import BytesIO
    from zipfile import ZipFile,ZIP_DEFLATED
    import json
    tasks,links,ids=demo();raw=export_work_backup(tasks,links,empty_logs(),empty_rules(),'UGV-001',{})
    with ZipFile(BytesIO(raw)) as archive:
        data=json.loads(archive.read('peims_work.json'))
    data['tasks'][0]['project_id']='DWP-002'
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as archive:
        archive.writestr('peims_work.json',json.dumps(data))
    with pytest.raises(ValueError,match='other-project'):
        import_work_backup(out.getvalue(),'UGV-001',tasks,links,empty_logs(),empty_rules(),{},ids)
