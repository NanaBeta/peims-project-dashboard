"""Cross-module integrity checks; no Streamlit runtime required."""
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analytics import DATASET_COLUMNS, compute, make_alerts, select_project, validated_frame, weekly_report


def load_data():
    return {name: validated_frame(name, pd.read_csv(ROOT / 'data' / f'{name}.csv')) for name in DATASET_COLUMNS}


def test_both_project_reports_and_registers():
    tables = load_data()
    for pid in tables['projects']['project_id']:
        outcome = compute(select_project(tables, pid))
        assert len(outcome['activities']) > 0
        assert len(outcome['procurement']) > 0
        assert len(outcome['risks']) > 0
        assert len(outcome['actions']) > 0
        assert len(outcome['history']) > 0
        assert outcome['kpi']['earned_value'] > 0
        assert outcome['kpi']['planned_value'] > 0
        assert len(make_alerts(outcome)) >= 1
        report = weekly_report(outcome)
        assert outcome['info']['project_name'] in report
        assert 'FICTIONAL DEMONSTRATION' in report
        assert 'not AI predictions' in report


def test_reference_ids_and_cost_integrity():
    tables = load_data()
    projects = set(tables['projects']['project_id'])
    for name in DATASET_COLUMNS:
        if name != 'projects':
            assert set(tables[name]['project_id']) <= projects, name
    assert set(tables['costs']['activity_id']) == set(tables['activities']['activity_id'])


def test_orphan_cost_row_rejected():
    data = load_data()
    d = select_project(data, 'UGV-001')
    extra = d['costs'].iloc[[0]].copy()
    extra['activity_id'] = 'UNKNOWN'
    d['costs'] = pd.concat([d['costs'], extra], ignore_index=True)
    with pytest.raises(ValueError, match='unmatched cost rows'):
        compute(d)


def test_duplicate_progress_timestamp_rejected():
    frame = load_data()['progress_history']
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match='Duplicate weekly snapshots'):
        validated_frame('progress_history', frame)


def test_noninteger_risk_scale_rejected():
    frame = load_data()['risks']
    frame['probability'] = frame['probability'].astype(float)
    frame.loc[0, 'probability'] = 2.5
    with pytest.raises(ValueError, match='whole numbers'):
        validated_frame('risks', frame)


def test_received_order_requires_date():
    frame = load_data()['procurement']
    frame.loc[0, 'status'] = 'Received'
    frame.loc[0, 'received_date'] = pd.NaT
    with pytest.raises(ValueError, match='received date'):
        validated_frame('procurement', frame)


def test_static_preview_embedded_numbers_match_python_engine():
    """The read-only Pages preview must not drift from Streamlit's sample calculation."""
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    match = re.search(r'const PROJECTS=(\{.*?\});\s*const pages=', html, re.DOTALL)
    assert match is not None, 'Static preview is missing its data payload'
    embedded = json.loads(match.group(1))
    tables = load_data()
    assert set(embedded) == set(tables['projects']['project_id'])
    for pid, record in embedded.items():
        result = compute(select_project(tables, pid))
        for key, value in result['kpi'].items():
            if value is None:
                assert record['kpi'][key] is None
            else:
                assert record['kpi'][key] == pytest.approx(value)
        assert result['info']['project_name'] in record['report']
        assert len(record['activities']) == len(result['activities'])
        assert len(record['procurement']) == len(result['procurement'])


def test_all_browser_preview_sections_are_defined():
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    for token in ('Command centre', 'Schedule', 'Cost control', 'Procurement', 'Risks & actions', 'Weekly report'):
        assert token in html
    for token in ('function overview(', 'function schedule(', 'function costs(', 'function procurement(', 'function risks(', 'function report(', 'function downloadReport('):
        assert token in html
