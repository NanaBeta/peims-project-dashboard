"""Streamlit integration checks; exercised in GitHub Actions after installing dependencies."""
from pathlib import Path

import pytest

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / 'app.py'


def test_every_dashboard_module_renders_for_each_project():
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception, [str(e.message) for e in at.exception]
    assert len(at.tabs) == 7
    assert len(at.sidebar.selectbox) == 1
    for pid in ('UGV-001', 'DWP-002'):
        at.sidebar.selectbox[0].set_value(pid).run()
        assert not at.exception, [str(e.message) for e in at.exception]
        assert len(at.tabs) == 7
        assert len(at.metric) >= 10
        assert len(at.button) >= 1  # reset and import controls
        assert len(at.file_uploader) == 1


def test_valid_data_import():
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception
    root = APP.parent
    csv = (root / 'data' / 'activities.csv').read_bytes()
    dataset_controls = [w for w in at.selectbox if w.label == 'Dataset']
    assert len(dataset_controls) == 1, 'Dataset selector not found'
    dataset_controls[0].set_value('activities').run()
    at.file_uploader[0].upload('activities.csv', csv, 'text/csv').run()
    matching = [b for b in at.button if 'Validate and apply' in b.label]
    assert matching
    matching[0].click().run()
    assert not at.exception
