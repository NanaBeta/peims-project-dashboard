"""Regression checks for viewport clipping in PEIMS v0.5.5.2."""
from pathlib import Path
import re
import tomllib
from ui_shell import render_css

ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_header_owns_the_top_inset():
    config = tomllib.loads((ROOT / '.streamlit/config.toml').read_text())
    # Streamlit automatically adds toolbar height to this native gap.
    assert config['theme']['paddingTop'] == '1.4rem'
    for compact in (False, True):
        css = render_css(compact)
        for rule in re.findall(r'\.block-container\s*\{([^{}]*)\}', css):
            assert not re.search(r'(?:^|;)\s*padding(?:-top)?\s*:', rule), rule
        assert 'padding-left:.85rem' in css
        assert 'padding-right:.85rem' in css


def test_sidebar_starts_responsive_and_home_has_two_across_cards():
    app = (ROOT / 'app.py').read_text()
    assert 'initial_sidebar_state="auto"' in app
    assert 'for start in range(0, len(HOME_CHOICES), 2):' in app
    assert 'st.columns(2, gap="medium")' in app
