"""Regression tests for creating validated records in Spreadsheet Studio."""
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from analytics import DATASET_COLUMNS, compute, select_project, validated_frame
from workflow import WORKFLOW_COLUMNS, validate_workflow
from sheet_engine import project_sheet, apply_sheet, workbook_bytes, imported_sheet

ROOT = Path(__file__).resolve().parents[1]


def records():
    core = {n: validated_frame(n, pd.read_csv(ROOT / 'data' / f'{n}.csv')) for n in DATASET_COLUMNS}
    pids = set(core['projects']['project_id'].astype(str))
    flow = {n: validate_workflow(n, pd.read_csv(ROOT / 'data' / f'{n}.csv'), pids) for n in WORKFLOW_COLUMNS}
    return core, flow


def append_one(frame, key, value):
    new = frame.iloc[[0]].copy()
    new[key] = value
    new['project_id'] = None
    return pd.concat([frame, new], ignore_index=True)


def test_add_activity_creates_linked_cost_and_recalculates_budget():
    core, flow = records()
    old = project_sheet(core, flow, 'activities', 'UGV-001')
    extra = append_one(old, 'activity_id', 'ACT-NEW-140')
    extra.loc[extra.activity_id.eq('ACT-NEW-140'), 'baseline_budget'] = 17000
    updated, _, events = apply_sheet(core, flow, 'activities', 'UGV-001', extra)
    matched = updated['costs'].loc[updated['costs'].activity_id.eq('ACT-NEW-140')]
    assert len(matched) == 1 and matched.iloc[0].project_id == 'UGV-001'
    assert matched.iloc[0].actual_cost == matched.iloc[0].committed_cost == 0
    assert compute(select_project(updated, 'UGV-001'))['kpi']['budget'] > compute(select_project(core, 'UGV-001'))['kpi']['budget']
    assert len([e for e in events if e['action'] == 'created']) == 2
    assert len(updated['activities'].loc[updated['activities'].project_id.eq('DWP-002')]) == len(core['activities'].loc[core['activities'].project_id.eq('DWP-002')])


@pytest.mark.parametrize('sheet,key,new_id', [('actions','action_id','ACTION-NEW-143'),
 ('risks','risk_id','RISK-NEW-143'), ('procurement','po_id','PO-NEW-143'),
 ('contractors','contractor_id','CTR-NEW-143'), ('rfis','rfi_id','RFI-NEW-143'),
 ('documents','document_id','DOC-NEW-143')])
def test_new_project_record_can_be_created_with_validated_fields(sheet,key,new_id):
    core, flow = records()
    old = project_sheet(core, flow, sheet, 'UGV-001')
    updated_core, updated_flow, events = apply_sheet(core, flow, sheet, 'UGV-001', append_one(old,key,new_id))
    updated = (updated_flow if sheet in WORKFLOW_COLUMNS else updated_core)[sheet]
    assert new_id in updated[key].tolist()
    assert updated.loc[updated[key].eq(new_id),'project_id'].iloc[0] == 'UGV-001'
    assert any(e['record_id'] == new_id and e['action'] == 'created' for e in events)


def test_rejects_duplicate_id_deletion_wrong_project_and_cost_only_append():
    core, flow = records()
    original = project_sheet(core, flow, 'actions', 'UGV-001')
    with pytest.raises(ValueError,match='Duplicate'):
        apply_sheet(core, flow, 'actions', 'UGV-001', pd.concat([original,original.iloc[[0]]],ignore_index=True))
    with pytest.raises(ValueError,match='deleted or renamed'):
        apply_sheet(core, flow, 'actions', 'UGV-001', original.iloc[:-1])
    wrong = append_one(original, 'action_id', 'WRONG-PROJECT')
    wrong.loc[wrong.action_id.eq('WRONG-PROJECT'),'project_id']='DWP-002'
    with pytest.raises(ValueError, match='selected project'):
        apply_sheet(core, flow, 'actions', 'UGV-001', wrong)
    costs = project_sheet(core, flow, 'costs', 'UGV-001')
    with pytest.raises(ValueError, match='automatically'):
        apply_sheet(core, flow, 'costs', 'UGV-001', append_one(costs, 'activity_id', 'UNLINKED-COST'))


def test_excel_workbook_accepts_appended_validated_action_row():
    core, flow = records()
    workbook = load_workbook(BytesIO(workbook_bytes(core, flow, 'UGV-001')))
    ws = workbook['actions']
    headers = [x.value for x in ws[1]]
    values = [x.value for x in ws[2]]
    values[headers.index('action_id')] = 'ACTION-XL-143'
    values[headers.index('project_id')] = None
    values[headers.index('action')] = 'Fictional additional inspection'
    ws.append(values)
    out = BytesIO()
    workbook.save(out)
    imported = imported_sheet(out.getvalue(), 'actions')
    updated, _, events = apply_sheet(core, flow, 'actions', 'UGV-001', imported)
    assert 'ACTION-XL-143' in updated['actions'].action_id.to_list()
    assert any(e['record_id'] == 'ACTION-XL-143' and e['action'] == 'created' for e in events)
