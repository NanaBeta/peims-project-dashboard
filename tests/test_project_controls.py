from pathlib import Path
import pandas as pd
import pytest
from project_controls import critical_path, cost_forecast

BASE = Path(__file__).resolve().parents[1]

def test_demo_networks_are_acyclic_and_have_float():
    activities=pd.read_csv(BASE/'data/activities.csv')
    links=pd.read_csv(BASE/'data/dependencies.csv')
    for pid in ('UGV-001','DWP-002'):
        x=critical_path(activities[activities.project_id==pid],links[links.project_id==pid])
        assert x['critical_activity_ids']
        assert all(r['total_float_days']>=0 for r in x['activities'])
        assert x['project_start']<=x['model_finish']

def test_finish_start_link_and_float():
    a=pd.DataFrame({'activity_id':['A','B','C'],'start_date':['2026-01-01']*3,
                    'finish_date':['2026-01-03','2026-01-02','2026-01-02']})
    links=pd.DataFrame([{'project_id':'P','predecessor_id':'A','successor_id':'B','lag_days':1}])
    x=critical_path(a,links)
    rows={r['activity_id']:r for r in x['activities']}
    assert rows['B']['earliest_start']=='2026-01-05'
    assert x['model_finish']=='2026-01-06'
    assert rows['C']['total_float_days']==4

def test_cycle_and_bad_links_rejected():
    a=pd.DataFrame({'activity_id':['A','B'],'start_date':['2026-01-01']*2,
                    'finish_date':['2026-01-02']*2})
    l=pd.DataFrame([{'project_id':'P','predecessor_id':'A','successor_id':'B','lag_days':0},
                    {'project_id':'P','predecessor_id':'B','successor_id':'A','lag_days':0}])
    with pytest.raises(ValueError,match='cycle'):critical_path(a,l)
    l.loc[1,'successor_id']='UNKNOWN'
    with pytest.raises(ValueError,match='unknown'):critical_path(a,l)

def test_cost_forecast_separates_commitments():
    x=cost_forecast(100,50,60,30)
    assert x['eac_cpi']==pytest.approx(120)
    assert x['vac_cpi']==pytest.approx(-20)
    assert x['commitments_unspent']==30
    assert x['ac']==60
    assert cost_forecast(100,0,0)['eac_cpi'] is None
    with pytest.raises(ValueError):cost_forecast(100,120,10)
