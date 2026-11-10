"""Data semantics, project isolation and regression tests for PEIMS Gantt."""
from pathlib import Path
import pandas as pd
import pytest
from analytics import DATASET_COLUMNS, validated_frame, select_project, compute
from gantt import gantt_rows, gantt_figure, STATUS_COLORS

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def project_results():
    core = {name: validated_frame(name, pd.read_csv(ROOT / 'data' / (name + '.csv')))
            for name in DATASET_COLUMNS}
    return {pid: compute(select_project(core, pid)) for pid in core['projects']['project_id']}

@pytest.mark.parametrize('pid', ['UGV-001', 'DWP-002'])
def test_full_chart_has_every_activity_and_planned_duration(project_results, pid):
    r = project_results[pid]
    rows = gantt_rows(r['activities'], r['date'])
    fig = gantt_figure(r['activities'], r['date'])
    assert len(rows) == len(r['activities'])
    assert set(rows['activity_id']) == set(r['activities']['activity_id'])
    assert len(fig.data) >= 2
    background = fig.data[0]
    assert background.name == 'Planned window'
    assert len(background.x) == len(rows)
    for ix, row in rows.iterrows():
        assert background.x[ix] == pytest.approx(row['duration_days'] * 86_400_000)
        assert pd.Timestamp(background.base[ix]) == row['start_date']
    assert 'Reporting date' in [a.text for a in fig.layout.annotations]
    assert len(fig.to_json()) > 1000

@pytest.mark.parametrize('pid', ['UGV-001', 'DWP-002'])
def test_home_preview_focus_and_no_cross_project_data(project_results, pid):
    r = project_results[pid]
    rows = gantt_rows(r['activities'], r['date'], focus=True, limit=5)
    fig = gantt_figure(r['activities'], r['date'], compact=True, limit=5)
    assert len(rows) <= 5
    assert len(fig.data[0].y) == len(rows)
    assert rows['activity_id'].is_unique
    assert set(rows['gantt_status']).issubset(STATUS_COLORS)
    assert not rows['project_id'].astype(str).ne(pid).any()

def test_progress_fill_is_reported_fraction_not_future_dates(project_results):
    r = project_results['UGV-001']
    rows = gantt_rows(r['activities'], r['date'])
    fig = gantt_figure(r['activities'], r['date'])
    for trace in fig.data[1:]:
        for label, duration in zip(trace.y, trace.x):
            row = rows.loc[rows['gantt_label'].eq(label)].iloc[0]
            expected = row['duration_days'] * 86_400_000 * row['actual_pct'] / 100
            assert duration == pytest.approx(expected)

def test_bad_dates_and_duplicated_ids_rejected(project_results):
    r = project_results['UGV-001']
    duplicate = pd.concat([r['activities'], r['activities'].head(1)])
    with pytest.raises(ValueError, match='unique activity IDs'):
        gantt_rows(duplicate, r['date'])
    invalid = r['activities'].copy()
    invalid.loc[invalid.index[0], 'finish_date'] = pd.Timestamp('1900-01-01')
    with pytest.raises(ValueError, match='date windows'):
        gantt_rows(invalid, r['date'])
