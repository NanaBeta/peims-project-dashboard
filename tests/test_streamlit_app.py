"""Cloud Streamlit AppTest coverage for focused navigation and data workflows."""
from pathlib import Path

import pytest

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / 'app.py'
PAGES = (
    'Home', 'Command centre', 'Schedule', 'Cost control', 'Procurement',
    'Risks & actions', 'Documents', 'Analytics studio', 'Reports', 'Workflows', 'Data studio',
)


def app_test():
    at = AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception, [str(e.message) for e in at.exception]
    assert len(at.sidebar.selectbox) == 1
    assert len(at.sidebar.radio) == 1
    return at


@pytest.mark.parametrize('project_id', ('UGV-001', 'DWP-002'))
def test_every_workspace_page_renders_with_each_project(project_id):
    at = app_test()
    at.sidebar.selectbox[0].set_value(project_id).run()
    assert not at.exception
    for page in PAGES:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, (project_id, page, [str(e.message) for e in at.exception])
        assert at.sidebar.radio[0].value == page
        if page in ('Command centre', 'Schedule', 'Cost control'):
            assert len(at.metric) >= 3
        if page == 'Workflows':
            assert len(at.tabs) >= 4  # Four workflow subtabs, no global tab ribbon.


def test_compact_layout_still_renders():
    at = app_test()
    toggles = [w for w in at.sidebar.toggle if w.label == 'Compact layout']
    assert len(toggles) == 1
    toggles[0].set_value(True).run()
    assert not at.exception


def test_valid_data_import_from_data_studio():
    at = app_test()
    at.sidebar.radio[0].set_value('Data studio').run()
    assert not at.exception
    csv = (APP.parent / 'data' / 'activities.csv').read_bytes()
    dataset_controls = [w for w in at.selectbox if w.label == 'Dataset']
    assert len(dataset_controls) == 1
    dataset_controls[0].set_value('activities').run()
    at.file_uploader[0].upload('activities.csv', csv, 'text/csv').run()
    matching = [b for b in at.button if 'Validate and apply' in b.label]
    assert matching
    matching[0].click().run()
    assert not at.exception


def test_overview_quick_navigation_uses_same_workspace_selector():
    at = app_test()
    assert at.sidebar.radio[0].value == "Home"
    schedule = [w for w in at.button if w.label.startswith("Manage schedule")]
    assert len(schedule) == 1
    schedule[0].click().run()
    assert not at.exception, [str(e.message) for e in at.exception]
    assert at.sidebar.radio[0].value == "Schedule"
    back = [w for w in at.button if w.label.startswith('← Home')]
    assert len(back) == 1
    back[0].click().run()
    assert not at.exception
    report = [w for w in at.button if w.label.startswith("Prepare a report")]
    assert len(report) == 1
    report[0].click().run()
    assert not at.exception
    assert at.sidebar.radio[0].value == "Reports"


def test_home_to_activity_detail_and_back():
    at = app_test()
    [b for b in at.button if b.label.startswith('Manage schedule')][0].click().run()
    assert not at.exception
    items = [b for b in at.button if b.label.startswith('1.1  ')]
    assert items
    items[0].click().run()
    assert not at.exception
    assert any(b.label == '← All activities' for b in at.button)
    [b for b in at.button if b.label == '← All activities'][0].click().run()
    assert not at.exception
    assert not any(b.label == '← All activities' for b in at.button)


def test_home_documents_and_actions_navigate():
    at = app_test()
    docs = [b for b in at.button if b.label.startswith('Open documents')]
    assert len(docs) == 1
    docs[0].click().run()
    assert not at.exception
    assert at.sidebar.radio[0].value == 'Documents'
    assert any(b.label.startswith('Ventilation fan GA') for b in at.button)
    at.sidebar.radio[0].set_value('Home').run()
    issues = [b for b in at.button if b.label.startswith('Resolve issues')]
    assert issues
    issues[0].click().run()
    assert not at.exception
    assert at.sidebar.radio[0].value == 'Risks & actions'
