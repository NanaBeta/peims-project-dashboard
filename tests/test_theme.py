"""Native appearance modes and palette / chart safety checks."""
from pathlib import Path
import tomllib
import plotly.graph_objects as go
from ui_shell import render_css
from visuals import _style, RED, GOLD, TEAL, BLUE

ROOT = Path(__file__).resolve().parents[1]

def _lum(x):
    c = [int(x[i:i+2],16)/255 for i in (1,3,5)]
    c = [v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c]
    return sum(a*b for a,b in zip(c,(.2126,.7152,.0722)))

def _contrast(a,b):
    x,y=sorted((_lum(a),_lum(b)))
    return (y+.05)/(x+.05)

def test_light_and_dark_presets():
    t=tomllib.loads((ROOT/'.streamlit/config.toml').read_text())['theme']
    assert t['base']=='dark'
    for mode in ('light','dark'):
        v=t[mode]
        assert _contrast(v['textColor'],v['backgroundColor'])>=4.5
        assert _contrast(v['sidebar']['textColor'],v['sidebar']['backgroundColor'])>=4.5
        assert _contrast('#FFFFFF',v['primaryColor'])>=4.5
        assert all(_contrast(v['secondaryBackgroundColor'],c)>=3 for c in (RED,GOLD,TEAL,BLUE))

def test_custom_css_is_theme_aware():
    css=render_css(False)
    assert 'var(--st-text-color' in css
    assert 'var(--st-background-color' in css
    assert 'peims-theme-tip' in css
    assert '#MainMenu {visibility:hidden}' not in css

def test_plotly_defers_text_to_native_theme():
    fig=_style(go.Figure(go.Scatter(x=[1,2],y=[2,1])))
    assert fig.layout.font.color is None
    assert fig.layout.hoverlabel.bgcolor is None
