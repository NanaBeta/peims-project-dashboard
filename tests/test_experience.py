"""Navigation-first helper checks independent of Streamlit Cloud."""
from pathlib import Path
import pandas as pd
from analytics import DATASET_COLUMNS, validated_frame, compute, select_project
from workflow import WORKFLOW_COLUMNS, validate_workflow
from experience import HOME_CHOICES, home_choice_counts, priority_actions, render_welcome, activity_status

ROOT = Path(__file__).resolve().parents[1]


def sample(project_id='UGV-001'):
    core={name:validated_frame(name,pd.read_csv(ROOT/'data'/f'{name}.csv')) for name in DATASET_COLUMNS}
    ids=set(core['projects']['project_id'].astype(str))
    workflows={name:validate_workflow(name,pd.read_csv(ROOT/'data'/f'{name}.csv'),ids) for name in WORKFLOW_COLUMNS}
    return compute(select_project(core,project_id)),workflows


def test_all_home_cards_have_routes_and_descriptions():
    assert len(HOME_CHOICES)==6
    assert len({c.target for c in HOME_CHOICES})==6
    assert HOME_CHOICES[0].label=='Manage schedule'
    assert {c.target for c in HOME_CHOICES}=={'Schedule','Cost control','Procurement','Risks & actions','Documents','Reports'}


def test_home_metrics_grounded_in_project_data():
    for project in ['UGV-001','DWP-002']:
        result,workflows=sample(project)
        m=home_choice_counts(result,workflows)
        assert m['Schedule']==f'{len(result["activities"])} activities'
        assert m['Documents']==f'{len(workflows["documents"].loc[workflows["documents"].project_id.eq(project)])} documents'
        assert int(m['Procurement'].split()[0])==int(result['kpi']['overdue_po'])


def test_welcome_escapes_html_and_limits_progress_bar():
    html=render_welcome({'project_name':'<script>bad</script>','display_date':'09 Nov 2026'},
                        {'actual_pct':150, 'planned_pct':-4, 'progress_gap':-3})
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'width:100.0%' in html
    assert 'left:0.0%' in html
    assert 'Ready to move things forward?' in html


def test_action_queue_sorts_by_overdue_then_priority():
    r,_=sample()
    q=priority_actions(r,100)
    assert all(q['status']!='Closed')
    assert len(q)<=len(r['actions'])
    assert q['overdue'].tolist()==sorted(q['overdue'].tolist(),reverse=True)


def test_activity_status_from_real_computed_rows():
    r,_=sample()
    items=r['activities']
    assert activity_status(items.loc[items.activity_id.eq('V01')].iloc[0])=='Completed'
    assert activity_status(items.loc[items.activity_id.eq('V05')].iloc[0])
