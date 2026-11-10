"""Project-scoped data-entry hints must never leak values or bypass validators."""
from pathlib import Path

import pandas as pd
import pytest

from analytics import DATASET_COLUMNS, validated_frame
from workflow import WORKFLOW_COLUMNS, validate_workflow
from smart_entry import suggestions, new_record_id, validate_smart_inputs
from sheet_engine import project_sheet, apply_sheet

DATA = Path(__file__).resolve().parents[1] / 'data'


def fixture():
    core = {k: validated_frame(k, pd.read_csv(DATA / f'{k}.csv')) for k in DATASET_COLUMNS}
    projects = set(core['projects']['project_id'].astype(str))
    workflow = {k: validate_workflow(k, pd.read_csv(DATA / f'{k}.csv'), projects) for k in WORKFLOW_COLUMNS}
    return core, workflow


def test_suggest_owner_from_related_current_project_registers():
    core, flows = fixture()
    owners = suggestions(core, flows, 'activities', 'UGV-001', 'owner')
    assert 'Electrical Engineer' in owners
    assert 'Mechanical Engineer' in owners
    assert 'Procurement Lead' in owners
    assert len(owners) == len(set(x.casefold() for x in owners))


def test_no_cross_project_leakage_and_user_new_values_available_after_save():
    core, flows = fixture()
    vals = project_sheet(core, flows, 'actions', 'DWP-002')
    vals.loc[vals.index[0], 'owner'] = 'DWP-ONLY-PRIVATE-OWNER'
    core['actions'].loc[core['actions']['project_id'].eq('DWP-002'), 'owner'] = vals.iloc[0]['owner']
    assert 'DWP-ONLY-PRIVATE-OWNER' not in suggestions(core, flows, 'actions', 'UGV-001','owner')
    assert 'DWP-ONLY-PRIVATE-OWNER' in suggestions(core, flows, 'actions', 'DWP-002','owner')
    curr = project_sheet(core, flows, 'actions', 'UGV-001')
    new = curr.iloc[[0]].copy()
    new.loc[:, 'action_id'] = new_record_id(core, flows, 'actions', 'UGV-001')
    new.loc[:, 'owner'] = 'New Mechanical Inspector'
    updated, _, events = apply_sheet(core, flows, 'actions', 'UGV-001', pd.concat([curr, new], ignore_index=True))
    assert any(e['action']=='created' for e in events)
    assert 'New Mechanical Inspector' in suggestions(updated, flows, 'actions', 'UGV-001', 'owner')


def test_known_disciplines_and_project_values_both_available():
    core, flows = fixture()
    s = suggestions(core, flows, 'rfis', 'UGV-001', 'discipline')
    assert 'Electrical' in s and 'Plumbing' in s and 'Civil' in s
    assert suggestions(core, flows, 'actions', 'UGV-001', 'action') == []


def test_new_ids_unique_global_and_scoped():
    core, flows = fixture()
    for sheet in ('activities', 'procurement', 'risks','actions','contractors','rfis','documents'):
        for pid in ('UGV-001','DWP-002'):
            rid = new_record_id(core, flows, sheet, pid)
            used = (core if sheet in core else flows)[sheet]
            assert rid not in set(used[{'activities':'activity_id','procurement':'po_id','risks':'risk_id','actions':'action_id','contractors':'contractor_id','rfis':'rfi_id','documents':'document_id'}[sheet]])
            assert len(rid) <= 48


def test_reject_blank_choice_and_unset_risk_assessment():
    for field in ('owner', 'status'):
        with pytest.raises(ValueError, match='required'):
            validate_smart_inputs('actions', {'action':'Inspect installation', 'priority':'High', 'status':'Open', 'owner':'Civil lead',field:None})
    with pytest.raises(ValueError,match='score'):
        validate_smart_inputs('risks', {'risk':'Delay','category':'Schedule','owner':'Engineer','status':'Open','probability':None,'impact':3})
    assert validate_smart_inputs('actions', {'action':' Review ', 'owner':'Electrical Engineer', 'priority':'High', 'status':'Open'})['action'] == 'Review'
