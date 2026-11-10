"""Project report-builder aggregations are deterministic and project-scoped."""
from pathlib import Path
import pandas as pd
import pytest
from analytics import DATASET_COLUMNS,compute,select_project,validated_frame
from bi_engine import SOURCE_SPECS, build_analysis, source_frame
ROOT=Path(__file__).resolve().parents[1]


def get_result(pid='UGV-001'):
    core={n:validated_frame(n,pd.read_csv(ROOT/'data'/f'{n}.csv')) for n in DATASET_COLUMNS}
    return compute(select_project(core,pid))


@pytest.mark.parametrize('pid',['UGV-001','DWP-002'])
def test_grouped_budget_sums_to_project_budget(pid):
    r=get_result(pid)
    s,d=build_analysis(r,'Activities','owner','Baseline budget')
    assert abs(s['Baseline budget'].sum()-r['kpi']['budget'])<1e-6
    assert len(d)==len(r['activities'])


def test_weighted_completion_matches_overview():
    r=get_result()
    s,_=build_analysis(r,'Activities','owner','Weighted completion (%)')
    # Compare one group independently against weighted source activities.
    owner=s['owner'].iloc[0]
    df=r['activities'].loc[r['activities'].owner.eq(owner)]
    want=round(float((df.weight*df.actual_pct).sum()/df.weight.sum()),1)
    assert s.loc[s.owner.eq(owner),'Weighted completion (%)'].iloc[0]==want


def test_procurement_overdue_sums_to_kpi():
    r=get_result()
    s,_=build_analysis(r,'Procurement','supplier','Overdue orders')
    assert s['Overdue orders'].sum()==r['kpi']['overdue_po']


def test_filtered_actions_are_exact_subset():
    r=get_result()
    owner=str(r['actions'].owner.iloc[0])
    s,d=build_analysis(r,'Actions','status','Action items','owner',owner)
    assert len(d)==sum(r['actions'].owner.eq(owner))
    assert s['Action items'].sum()==len(d)


def test_reject_unregistered_expressions_and_sources():
    r=get_result()
    with pytest.raises(ValueError):
        build_analysis(r,'Activities','__import__','Actual expenditure')
    with pytest.raises(ValueError):
        build_analysis(r,'unknown','owner','Action items')
    with pytest.raises(ValueError):
        build_analysis(r,'Activities','owner','Budget',filter_column='__dict__',filter_value='a')
