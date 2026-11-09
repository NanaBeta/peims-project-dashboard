"""PEIMS UI shell: navigation consistency, safe text and honest snapshot status."""

import pytest
from ui_shell import (
    NAVIGATION, NAV_LABELS, PAGE_INFO, attention_flags, render_brand,
    render_css, render_header, render_intro, render_safety, render_footer,
)


def test_navigation_complete_unique_and_described():
    assert len(NAVIGATION) == 9
    assert len(set(NAVIGATION)) == len(NAVIGATION)
    assert set(NAVIGATION) == set(NAV_LABELS) == set(PAGE_INFO)
    assert all(len(PAGE_INFO[page]) == 3 for page in NAVIGATION)
    assert all("peims-section-title" in render_intro(page) for page in NAVIGATION)


def test_no_unsubstantiated_health_score():
    all_clear = {"progress_gap": 0, "open_high_risks": 0, "overdue_po": 0, "overdue_actions": 0}
    assert attention_flags(all_clear) == ("No flagged exceptions", "neutral", 0)
    issues = dict(all_clear, progress_gap=-6, overdue_po=2, open_high_risks=1)
    label, tone, count = attention_flags(issues)
    assert (label, tone, count) == ("Review required", "warning", 3)
    assert attention_flags({"progress_gap": -5})[2] == 0


def test_project_header_escapes_untrusted_text_and_bounds_visual_progress():
    project = {"project_name": '<script>alert("x")</script>', "location": "<img src=x>",
               "type": "Underground", "project_id": "P-001", "display_date": "09 Nov 2026"}
    kpi = {"actual_pct": 125, "planned_pct": 78, "progress_gap": 47}
    html = render_header(project, kpi)
    assert "<script>" not in html and "<img src" not in html
    assert '&lt;script&gt;' in html
    assert 'width:100.0%' in html
    assert 'aria-label="Selected project overview"' in html
    assert 'P-001' in html


def test_styles_are_closed_responsive_and_compact_is_real():
    normal, compact = render_css(False), render_css(True)
    assert normal.startswith('<style>') and normal.endswith('</style>')
    assert '@media (max-width:800px)' in normal
    assert '@media (prefers-reduced-motion: reduce)' in normal
    assert compact != normal
    assert 'min-height: 78px' in compact
    assert 'WORKSPACE' in render_brand() or 'PROJECT INTELLIGENCE' in render_brand()
    assert 'No Newmont integration' in render_safety()
    assert 'Public demo data is not persistent' in render_footer()
