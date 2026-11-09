"""Headless unit-smoke of every panel without installing Streamlit.

This calls each dashboard render function and checks Plotly chart serialization,
but does not replace a real browser or Streamlit integration test.
"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analytics import DATASET_COLUMNS, compute, select_project, validated_frame


class FakeStreamlit(ModuleType):
    def __init__(self):
        super().__init__('streamlit')
        self.session_state = {}
        self.sidebar = self
        self.events = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def set_page_config(self, **kwargs):
        pass

    def cache_data(self, **kwargs):
        return lambda f: f

    def columns(self, n, **kwargs):
        return [self] * (n if isinstance(n, int) else len(n))

    def tabs(self, names):
        return [self] * len(names)

    def container(self, **kwargs):
        return self

    def expander(self, *args, **kwargs):
        return self

    def metric(self, *args, **kwargs):
        self.events.append('metric')

    def plotly_chart(self, fig, **kwargs):
        fig.to_plotly_json()  # confirms the chart is serializable
        self.events.append('plotly_chart')

    def dataframe(self, frame, **kwargs):
        assert isinstance(frame, pd.DataFrame)
        self.events.append('dataframe')

    def download_button(self, *args, **kwargs):
        self.events.append('download_button')
        return False

    def selectbox(self, label, options, **kwargs):
        return list(options)[0]

    def file_uploader(self, *args, **kwargs):
        return None

    def button(self, *args, **kwargs):
        return False

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def test_all_seven_render_panels_for_both_projects(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setitem(sys.modules, 'streamlit', fake)
    spec = importlib.util.spec_from_file_location('peims_panel_smoke', ROOT / 'app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    tables = {name: validated_frame(name, pd.read_csv(ROOT / 'data' / f'{name}.csv')) for name in DATASET_COLUMNS}
    for pid in tables['projects']['project_id']:
        result = compute(select_project(tables, pid))
        for method in (module.show_overview, module.show_schedule, module.show_financials,
                       module.show_procurement, module.show_risks, module.show_reports):
            before = len(fake.events)
            method(result)
            assert len(fake.events) > before, (pid, method.__name__)
        before = len(fake.events)
        module.show_data_controls(tables)
        assert len(fake.events) > before
    assert fake.events.count('plotly_chart') >= 8
    assert fake.events.count('dataframe') >= 10
    assert fake.events.count('download_button') >= 6
