"""Excel-inspired project-scoped editing and workbook exchange tests."""
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from analytics import DATASET_COLUMNS, compute, select_project, validated_frame
from workflow import WORKFLOW_COLUMNS, validate_workflow
from sheet_engine import (SHEET_NAMES, EDITABLE_SHEETS, project_sheet, apply_sheet,
                          workbook_bytes, imported_sheet)

ROOT = Path(__file__).resolve().parents[1]


def fixture_data():
    core = {n:validated_frame(n,pd.read_csv(ROOT/'data'/f'{n}.csv')) for n in DATASET_COLUMNS}
    ids = set(core['projects']['project_id'].astype(str))
    workflow = {n:validate_workflow(n,pd.read_csv(ROOT/'data'/f'{n}.csv'),ids) for n in WORKFLOW_COLUMNS}
    return core,workflow


def test_export_has_project_scoped_named_worksheets_and_safe_strings():
    core, workflows = fixture_data()
    b = workbook_bytes(core, workflows, 'UGV-001')
    assert b[:2] == b'PK'
    w = load_workbook(BytesIO(b), read_only=True)
    assert set(SHEET_NAMES) | {'Guide'} == set(w.sheetnames)
    assert w['Guide']['B3'].value == 'UGV-001'
    assert w['activities'].max_row == len(project_sheet(core,workflows,'activities','UGV-001'))+1
    assert w['actions'].max_row == len(project_sheet(core,workflows,'actions','UGV-001'))+1
    assert len(project_sheet(core,workflows,'procurement','UGV-001')) != len(core['procurement'])
    w.close()


def test_roundtrip_import_does_not_change_project_records():
    core,flow = fixture_data()
    payload=workbook_bytes(core,flow,'UGV-001')
    for name in EDITABLE_SHEETS:
        df=imported_sheet(payload,name)
        new_core,new_flow,events=apply_sheet(core,flow,name,'UGV-001',df)
        assert not events, (name,events)
        assert new_core['projects'].equals(core['projects'])
        assert new_flow['documents'].shape == flow['documents'].shape


def test_activity_edit_recalculates_kpis_but_does_not_mutate_other_project():
    core,flow=fixture_data()
    old=compute(select_project(core,'UGV-001'))['kpi']['actual_pct']
    other=core['activities'].loc[core['activities'].project_id.eq('DWP-002')].copy()
    df=project_sheet(core,flow,'activities','UGV-001')
    target = df.index[-1]
    df.loc[target,'actual_pct']=min(100,float(df.loc[target,'actual_pct'])+25)
    updated,_,events=apply_sheet(core,flow,'activities','UGV-001',df)
    assert len(events)==1
    assert compute(select_project(updated,'UGV-001'))['kpi']['actual_pct']>old
    pd.testing.assert_frame_equal(updated['activities'].loc[updated['activities'].project_id.eq('DWP-002')].reset_index(drop=True),other.reset_index(drop=True))


def test_project_id_changes_are_rejected():
    core,flow=fixture_data()
    sheet=project_sheet(core,flow,'actions','UGV-001')
    sheet.loc[0,'project_id']='DWP-002'
    with pytest.raises(ValueError, match='project'):
        apply_sheet(core,flow,'actions','UGV-001',sheet)


def test_identity_and_row_count_changes_are_rejected():
    core,flow=fixture_data()
    sheet=project_sheet(core,flow,'costs','UGV-001')
    sheet.loc[0,'activity_id']='FORGED'
    with pytest.raises(ValueError,match='IDs'):
        apply_sheet(core,flow,'costs','UGV-001',sheet)
    with pytest.raises(ValueError,match='IDs'):
        apply_sheet(core,flow,'costs','UGV-001',sheet.iloc[:-1])


def test_invalid_progress_and_inconsistent_costs_rejected():
    core,flow=fixture_data()
    acts=project_sheet(core,flow,'activities','UGV-001')
    acts.loc[0,'actual_pct']=150
    with pytest.raises(ValueError,match='between'):
        apply_sheet(core,flow,'activities','UGV-001',acts)
    costs=project_sheet(core,flow,'costs','UGV-001')
    costs.loc[0,'actual_cost']=-100
    with pytest.raises(ValueError,match='negative'):
        apply_sheet(core,flow,'costs','UGV-001',costs)


def test_workflow_changes_are_audited_and_preserve_other_project():
    core,flow=fixture_data()
    edited=project_sheet(core,flow,'rfis','UGV-001')
    edited.loc[0,'status']='In Review'
    new_core,new_flow,events=apply_sheet(core,flow,'rfis','UGV-001',edited)
    assert new_core['activities'].equals(core['activities'])
    assert len(events) <= 1
    assert len(new_flow['rfis'])==len(flow['rfis'])
    assert set(new_flow['rfis'].project_id)=={'UGV-001','DWP-002'}


def test_excel_formula_cells_cannot_be_imported():
    core,flow=fixture_data()
    b=workbook_bytes(core,flow,'UGV-001')
    wb=load_workbook(BytesIO(b))
    wb['actions']['C2']='=HYPERLINK("https://malicious.test","click")'
    o=BytesIO();wb.save(o)
    with pytest.raises(ValueError,match='Formula'):
        imported_sheet(o.getvalue(),'actions')


def test_bad_sheet_and_bad_bytes_rejected():
    with pytest.raises(ValueError):
        imported_sheet(b'abcd','actions')
    with pytest.raises(ValueError,match='not editable'):
        imported_sheet(b'whatever','progress_history')
    core,flow=fixture_data()
    with pytest.raises(ValueError):
        project_sheet(core,flow,'unknown','UGV-001')


def test_safe_csv_escapes_excel_formula_injection():
    from sheet_engine import safe_csv
    df = pd.DataFrame({'task':['=2+2', '+SUM(A1:A2)', '@evil', 'normal'], 'cost':[-9,0,8,12]})
    out = safe_csv(df)
    assert "'=2+2" in out and "'+SUM(A1:A2)" in out and "'@evil" in out
    assert '-9' in out
