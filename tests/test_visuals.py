"""Validate the *meaning* of analytical figures, not merely their ability to render."""
import numpy as np
import pandas as pd
import pytest

from analytics import DATASET_COLUMNS, validated_frame, compute, select_project
from project_controls import critical_path
from visuals import (
    progress_s_curve, schedule_variance, dependency_timeline,
    cost_variance_waterfall, cost_exposure_quadrant,
    procurement_delivery_map, risk_severity_matrix, insight_summary,
)
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def data():
    return {k:validated_frame(k,pd.read_csv(ROOT/'data'/f'{k}.csv')) for k in DATASET_COLUMNS}

@pytest.mark.parametrize('project_id',['UGV-001','DWP-002'])
def test_seven_charts_are_serializable_and_scoped(data, project_id):
    r=compute(select_project(data,project_id))
    acts=r['activities']
    dependencies=pd.read_csv(ROOT/'data'/'dependencies.csv')
    cpm=critical_path(acts,dependencies.loc[dependencies['project_id'].eq(project_id)])
    funcs=[
        progress_s_curve(r['history'],r['date']),
        schedule_variance(acts),
        dependency_timeline(acts,cpm,r['date']),
        cost_variance_waterfall(r['kpi'],r['info']['currency']),
        cost_exposure_quadrant(acts,r['info']['currency']),
        procurement_delivery_map(r['procurement'],r['date'],r['info']['currency']),
        risk_severity_matrix(r['risks']),
    ]
    for fig in funcs:
        assert len(fig.data)>0
        assert len(fig.to_json())>1000
    assert len(insight_summary(r))>=1

@pytest.mark.parametrize('project_id',['UGV-001','DWP-002'])
def test_progress_curve_only_uses_reported_dates(data,project_id):
    r=compute(select_project(data,project_id))
    f=progress_s_curve(r['history'],r['date'])
    history=r['history']
    for trace in f.data:
        assert list(pd.to_datetime(trace.x))==list(pd.to_datetime(history['week_ending']))
    assert len(f.data)==2

@pytest.mark.parametrize('project_id',['UGV-001','DWP-002'])
def test_schedule_plot_has_reference_and_actual_for_every_activity(data,project_id):
    r=compute(select_project(data,project_id))
    f=schedule_variance(r['activities'])
    assert len(f.data[-2].x)==len(r['activities'])
    assert len(f.data[-1].x)==len(r['activities'])
    assert np.allclose(np.array(f.data[-2].x,dtype=float),r['activities'].sort_values('variance_pp',ascending=False)['planned_pct'])

@pytest.mark.parametrize('project_id',['UGV-001','DWP-002'])
def test_cost_bridge_exactly_reconciles_ac_to_ev(data,project_id):
    r=compute(select_project(data,project_id))
    f=cost_variance_waterfall(r['kpi'],r['info']['currency'])
    ac,cv,_=f.data[0].y
    assert ac+cv==pytest.approx(r['kpi']['earned_value'])
    assert cv==pytest.approx(r['kpi']['cost_variance'])
    assert list(f.data[0].measure)==['absolute','relative','total']

@pytest.mark.parametrize('project_id',['UGV-001','DWP-002'])
def test_risk_matrix_background_is_score_but_text_is_open_count(data,project_id):
    r=compute(select_project(data,project_id))
    f=risk_severity_matrix(r['risks'])
    heat=f.data[0]
    assert heat.z[4][4]==25
    assert sum(sum(row) for row in heat.text)==int(r['risks']['open'].sum())
    assert heat.z[0][0]==1

@pytest.mark.parametrize('project_id',['UGV-001','DWP-002'])
def test_procurement_bubbles_each_order_once(data,project_id):
    r=compute(select_project(data,project_id))
    f=procurement_delivery_map(r['procurement'],r['date'],r['info']['currency'])
    ids=[row[0] for trace in f.data for row in trace.customdata]
    assert sorted(ids)==sorted(r['procurement']['po_id'])
    assert all(size>0 for t in f.data for size in t.marker.size)


def test_visuals_reject_no_future_point_imputation(data):
    r=compute(select_project(data,'UGV-001'))
    hist=r['history'].copy()
    fig=progress_s_curve(hist,r['date'])
    assert max(pd.to_datetime(fig.data[0].x)) <= max(pd.to_datetime(hist['week_ending']))
