"""v0.3 contractor, RFI, document and workspace safety checks."""
from pathlib import Path
import io
import sys
from zipfile import ZipFile

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analytics import DATASET_COLUMNS, validated_frame, compute, select_project
from workflow import (WORKFLOW_COLUMNS, validate_workflow, workflow_metrics,
                      apply_project_register, make_snapshot, read_snapshot)


def data():
    core = {n: validated_frame(n, pd.read_csv(ROOT / 'data' / f'{n}.csv')) for n in DATASET_COLUMNS}
    ids = set(core['projects']['project_id'])
    flows = {n: validate_workflow(n, pd.read_csv(ROOT / 'data' / f'{n}.csv'), ids) for n in WORKFLOW_COLUMNS}
    return core, flows


def test_all_new_registers_validate_for_both_projects():
    core, flows = data()
    for project_id in core['projects']['project_id']:
        m = workflow_metrics(flows, project_id, '2026-11-09')
        assert m['contractors'] > 0
        assert m['pending_rfis'] > 0
        assert m['documents'] > 0
        assert m['pending_documents'] >= 1


def test_editing_preserves_other_projects_and_logs_only_changes():
    core, flows = data()
    original = flows['contractors']
    project_id = 'UGV-001'
    edited = original.loc[original['project_id'].eq(project_id)].drop(columns=['project_id']).copy()
    edited.loc[edited['contractor_id'].eq('CTR-101'), 'status'] = 'At Risk'
    result, history = apply_project_register('contractors', original, edited, project_id,
                                             set(core['projects']['project_id']))
    assert len(history) == 1
    assert history[0]['record_id'] == 'CTR-101'
    assert history[0]['action'] == 'updated'
    assert result.loc[result['contractor_id'].eq('CTR-101'), 'status'].item() == 'At Risk'
    other_before = original.loc[original['project_id'].eq('DWP-002')]
    other_after = result.loc[result['project_id'].eq('DWP-002')]
    pd.testing.assert_frame_equal(other_before.reset_index(drop=True), other_after.reset_index(drop=True))


def test_reject_invalid_ids_dates_and_status():
    core, flows = data()
    ids = set(core['projects']['project_id'])
    c = flows['contractors'].copy()
    c.loc[0, 'progress_pct'] = 101
    with pytest.raises(ValueError, match='between 0 and 100'):
        validate_workflow('contractors', c, ids)
    r = flows['rfis'].copy()
    r.loc[0, 'due_date'] = '2020-01-01'
    with pytest.raises(ValueError, match='precede'):
        validate_workflow('rfis', r, ids)
    d = flows['documents'].copy()
    d.loc[0, 'project_id'] = 'NOT-A-PROJECT'
    with pytest.raises(ValueError, match='unknown'):
        validate_workflow('documents', d, ids)
    d = flows['documents'].copy()
    d.loc[0, 'status'] = 'secretly approved'
    with pytest.raises(ValueError, match='not allowed'):
        validate_workflow('documents', d, ids)


def test_snapshot_roundtrip_and_rejects_extra_files():
    core, flows = data()
    snap = make_snapshot(core, flows, [], list(DATASET_COLUMNS))
    restored_core, restored_flows, history = read_snapshot(snap, list(DATASET_COLUMNS),
                                                  validated_frame, compute, select_project)
    assert set(restored_core) == set(core)
    assert history == []
    for name in WORKFLOW_COLUMNS:
        assert len(restored_flows[name]) == len(flows[name])
    malicious = io.BytesIO()
    with ZipFile(io.BytesIO(snap)) as source, ZipFile(malicious, 'w') as target:
        for f in source.namelist():
            target.writestr(f, source.read(f))
        target.writestr('../surprise.txt', 'not allowed')
    with pytest.raises(ValueError, match='Unexpected'):
        read_snapshot(malicious.getvalue(), list(DATASET_COLUMNS),
                      validated_frame, compute, select_project)


def test_report_appendix_and_snapshot_history():
    from workflow import workflow_report_appendix
    core, flows = data()
    result = compute(select_project(core, 'UGV-001'))
    text = workflow_report_appendix(flows, 'UGV-001', result['date'])
    assert 'Engineering workflow summary' in text
    assert 'RFI-101' in text
    history = [{'timestamp_utc':'2026-11-09T16:00:00+00:00', 'actor':'demo_session',
                'project_id':'UGV-001','register':'rfis','record_id':'RFI-101','action':'updated'}]
    snap = make_snapshot(core, flows, history, list(DATASET_COLUMNS))
    _, _, loaded = read_snapshot(snap, list(DATASET_COLUMNS),
                                 validated_frame, compute, select_project)
    assert loaded == history
