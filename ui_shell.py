"""PEIMS public demonstration UI shell.

Presentation-only helpers. No database calls, network requests, access-control claims,
or changes to analytical records are made here.
"""
from __future__ import annotations

from html import escape

NAVIGATION = (
    "Command centre",
    "Schedule",
    "Cost control",
    "Procurement",
    "Risks & actions",
    "Analytics studio",
    "Reports",
    "Workflows",
    "Data studio",
)

NAV_LABELS = {
    "Command centre": "◈   Command centre",
    "Schedule": "▤   Planning & schedule",
    "Cost control": "◉   Cost & commercial",
    "Procurement": "▣   Procurement",
    "Risks & actions": "⚑   Risks & actions",
    "Analytics studio": "◫   Analytics studio",
    "Reports": "▧   Reports",
    "Workflows": "▦   Workflows",
    "Data studio": "⚙   Data studio",
}

PAGE_INFO = {
    "Command centre": ("PORTFOLIO INTELLIGENCE", "Command centre", "Monitor performance, exceptions and decisions from one consolidated view."),
    "Schedule": ("PROJECT DELIVERY", "Planning & schedule", "Inspect actual completion, dependencies, criticality and baseline slippage."),
    "Cost control": ("PROJECT COMMERCIAL", "Cost & commercial", "Connect financial performance, earned value and forecast scenarios."),
    "Procurement": ("SUPPLY CHAIN", "Procurement", "Follow overdue deliveries, critical equipment and purchase-order exposure."),
    "Risks & actions": ("ASSURANCE", "Risks & actions", "Prioritize open risks, accountable owners and overdue action items."),
    "Analytics studio": ("PROJECT INTELLIGENCE", "Analytics studio", "Explore cross-discipline project controls with work-package filters."),
    "Reports": ("REPORTING", "Reports", "Generate a traceable draft based on the selected project snapshot."),
    "Workflows": ("ENGINEERING COORDINATION", "Workflows", "Maintain demonstration contractor, RFI and document registers."),
    "Data studio": ("DATA GOVERNANCE", "Data studio", "Inspect sample records and validate session-only data imports."),
}


def attention_flags(kpi: dict) -> tuple[str, str, int]:
    """Count *types of exception*, never imply a certified project health score."""
    signals = (
        float(kpi.get("progress_gap", 0) or 0) < -5,
        int(kpi.get("open_high_risks", 0) or 0) > 0,
        int(kpi.get("overdue_po", 0) or 0) > 0,
        int(kpi.get("overdue_actions", 0) or 0) > 0,
    )
    n = sum(signals)
    if n:
        return "Review required", "warning", n
    return "No flagged exceptions", "neutral", 0


def render_css(compact: bool = False) -> str:
    density = """
    .block-container { padding-top: .85rem !important; }
    [data-testid="stMetric"] { padding: .65rem .9rem !important; min-height: 78px; }
    .peims-hero { padding: 1.05rem 1.2rem !important; }
    """ if compact else ""
    return """<style>
    :root {
      --peims-canvas:var(--st-background-color,transparent);
      --peims-surface:var(--st-secondary-background-color,transparent);
      --peims-sidebar:var(--st-secondary-background-color,transparent);
      --peims-border:var(--st-border-color,rgba(125,145,165,.26));
      --peims-ink:var(--st-text-color,currentColor);
      --peims-muted:var(--st-text-color,currentColor);
      --peims-accent:var(--st-link-color,var(--st-primary-color,#86540B));
    }
    html,body,[data-testid="stAppViewContainer"] { font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    .block-container {max-width:1500px;padding:1.25rem 2.0rem 3.5rem;}
    h1,h2,h3 {letter-spacing:-.035em;color:var(--peims-ink);}
    h1 {font-size:2rem !important;font-weight:750 !important;line-height:1.2 !important;}
    h2 {font-size:1.45rem !important;font-weight:720 !important;}
    h3 {font-size:1.12rem !important;font-weight:680 !important;}
    [data-testid="stSidebar"] > div:first-child {padding-top:1.3rem;}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {gap:.24rem;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {border-radius:9px;padding:.38rem .55rem;transition:background .15s ease;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background:var(--peims-surface);}
    [data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"] {background:var(--peims-surface);}
    [data-testid="stSidebar"] hr {border-color:var(--peims-border);}
    [data-testid="stMetric"] {background:var(--peims-surface);border:1px solid var(--peims-border);
      border-radius:13px;padding:1rem 1.1rem;min-height:100px;box-shadow:0 8px 22px rgba(0,0,0,.08);}
    [data-testid="stMetricLabel"] {color:var(--peims-muted) !important;font-weight:530;font-size:.82rem;}
    [data-testid="stMetricValue"] {color:var(--peims-ink) !important;letter-spacing:-.04em;font-weight:760;}
    [data-testid="stMetricDelta"] {font-size:.79rem;}
    [data-testid="stPlotlyChart"] {background:var(--peims-surface);border:1px solid var(--peims-border);
      border-radius:13px;padding:.45rem .65rem .2rem;}
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] {border:1px solid var(--peims-border);border-radius:11px;overflow:hidden;}
    [data-testid="stForm"], [data-testid="stExpander"], [data-testid="stVerticalBlockBorderWrapper"] {border-radius:12px;}
    [data-testid="stButton"] button,[data-testid="stDownloadButton"] button {border-radius:9px;font-weight:600;}
    [data-testid="stButton"] button:hover,[data-testid="stDownloadButton"] button:hover {border-color:var(--peims-accent);}
    [data-testid="stCaptionContainer"] {color:var(--peims-muted);line-height:1.5;}
    .peims-brand {display:flex;align-items:center;gap:.8rem;padding:.1rem 0 .6rem;}
    .peims-brand-mark {width:41px;height:41px;border-radius:11px;display:grid;place-items:center;
      background:linear-gradient(140deg,#eed18b,#b77d2e);color:#132038;font-size:17px;font-weight:900;}
    .peims-brand-title {font-size:1.13rem;font-weight:800;letter-spacing:.12em;color:var(--peims-ink);}
    .peims-brand-sub {font-size:.68rem;color:var(--peims-muted);letter-spacing:.06em;}
    .peims-sidebar-heading {font-size:.64rem;color:var(--peims-muted);letter-spacing:.16em;font-weight:800;margin:1rem 0 .2rem;}
    .peims-theme-tip {border-left:3px solid var(--peims-accent);padding:.35rem .65rem;font-size:.74rem;line-height:1.5;margin:.35rem 0 .8rem;}
    .peims-sidebar-note {background:var(--peims-surface);border:1px solid var(--peims-border);border-radius:10px;
       padding:.75rem .8rem;font-size:.75rem;line-height:1.5;color:var(--peims-muted);}
    .peims-hero {padding:1.35rem 1.65rem 1.2rem;border:1px solid var(--peims-border);border-radius:17px;
       background:linear-gradient(112deg,var(--peims-surface),var(--peims-surface) 70%);
       box-shadow:0 18px 36px rgba(4,12,22,.14);margin:0 0 .95rem;}
    .peims-hero-top {display:flex;align-items:center;justify-content:space-between;gap:.8rem;flex-wrap:wrap;}
    .peims-eyebrow {font-size:.67rem;color:var(--peims-accent);font-weight:800;letter-spacing:.17em;}
    .peims-badge {display:inline-flex;align-items:center;gap:.4rem;border:1px solid var(--peims-border);
       background:var(--peims-surface);border-radius:99px;padding:.28rem .68rem;color:var(--peims-ink);font-size:.71rem;font-weight:720;letter-spacing:.03em;}
    .peims-badge.warning {background:color-mix(in srgb,#b77a29 12%,var(--peims-surface));border-color:var(--peims-border);color:var(--peims-accent);}
    .peims-badge.neutral {background:var(--peims-surface);border-color:var(--peims-border);color:var(--peims-ink);}
    .peims-hero-title {font-size:clamp(1.35rem,2.2vw,2rem);font-weight:760;letter-spacing:-.045em;
       color:var(--peims-ink);line-height:1.2;margin:.68rem 0 .4rem;}
    .peims-hero-sub {font-size:.83rem;color:var(--peims-muted);line-height:1.5;}
    .peims-info-row {display:flex;align-items:center;gap:.65rem;flex-wrap:wrap;margin-top:1rem;}
    .peims-info-chip {font-size:.72rem;color:var(--peims-ink);background:var(--peims-canvas);border:1px solid var(--peims-border);
       border-radius:8px;padding:.35rem .65rem;}
    .peims-info-chip strong{color:var(--peims-ink);}
    .peims-progress {height:6px;background:var(--peims-border);border-radius:20px;overflow:hidden;margin-top:1.1rem;}
    .peims-progress > span {display:block;height:100%;background:linear-gradient(90deg,#d9a04b,#5ed4c4);border-radius:20px;}
    .peims-safety {display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;
       border-radius:9px;border:1px solid var(--peims-border);background:var(--peims-surface);
       padding:.65rem .85rem;color:var(--peims-muted);font-size:.74rem;margin:0 0 1.05rem;}
    .peims-safety strong {color:var(--peims-accent);letter-spacing:.03em;}
    .peims-section {margin:.35rem 0 1.15rem;}
    .peims-section-kicker {font-size:.68rem;color:var(--peims-accent);letter-spacing:.13em;font-weight:800;margin-bottom:.23rem;}
    .peims-section-title {font-size:1.34rem;font-weight:750;color:var(--peims-ink);letter-spacing:-.04em;}
    .peims-section-text {font-size:.85rem;color:var(--peims-muted);margin-top:.12rem;}
    .peims-footer {border-top:1px solid var(--peims-border);padding:1rem 0;color:var(--peims-muted);font-size:.74rem;line-height:1.65;margin-top:1.2rem;}
    .peims-alert {padding:.78rem .95rem;border-radius:10px;border-left:3px solid var(--peims-accent);
       background:var(--peims-surface);margin:.55rem 0;color:var(--peims-ink);font-size:.83rem;line-height:1.5;}
    .peims-alert strong {color:var(--peims-accent);font-size:.8rem;}
    .peims-alert small {color:var(--peims-muted);display:block;margin-top:.24rem;}
    @media (max-width:800px) {
      .block-container{padding:.8rem .85rem 2.4rem;}
      .peims-hero{padding:1rem .95rem;}
      .peims-hero-title{font-size:1.48rem;}
      [data-testid="stMetric"] {min-height:83px;padding:.7rem .78rem;}
      .peims-info-chip {font-size:.69rem;}
    }
    @media (prefers-reduced-motion: reduce) { * {scroll-behavior:auto !important;transition:none !important;} }
    """ + density + "</style>"


def render_brand() -> str:
    return ("<div class='peims-brand'><div class='peims-brand-mark'>P</div>"
            "<div><div class='peims-brand-title'>PEIMS</div>"
            "<div class='peims-brand-sub'>PROJECT INTELLIGENCE</div></div></div>")


def render_header(project: dict, kpi: dict) -> str:
    """Render an escaped, display-only header from a *fictional* project snapshot."""
    label, tone, n = attention_flags(kpi)
    name = escape(str(project.get("project_name", "Untitled project")))
    project_id = escape(str(project.get("project_id", "—")))
    location = escape(str(project.get("location", "—")))
    kind = escape(str(project.get("type", "Engineering project")))
    date = escape(str(project.get("display_date", "—")))
    progress = max(0., min(100., float(kpi.get("actual_pct", 0) or 0)))
    planned = float(kpi.get("planned_pct", 0) or 0)
    gap = float(kpi.get("progress_gap", 0) or 0)
    return f"""
    <div class="peims-hero" role="region" aria-label="Selected project overview">
      <div class="peims-hero-top"><span class="peims-eyebrow">WORKSPACE / PROJECT CONTROLS</span>
        <span class="peims-badge {tone}">{escape(label)} · {n} exception categories</span></div>
      <div class="peims-hero-title">{name}</div>
      <div class="peims-hero-sub">{kind} &nbsp;·&nbsp; {location}</div>
      <div class="peims-info-row">
        <span class="peims-info-chip">Project ID <strong>{project_id}</strong></span>
        <span class="peims-info-chip">Snapshot <strong>{date}</strong></span>
        <span class="peims-info-chip">Actual <strong>{progress:.1f}%</strong></span>
        <span class="peims-info-chip">Linear baseline <strong>{planned:.1f}%</strong></span>
        <span class="peims-info-chip">Gap <strong>{gap:+.1f} pp</strong></span>
      </div>
      <div class="peims-progress" role="progressbar" aria-label="Recorded physical progress"
        aria-valuemin="0" aria-valuemax="100" aria-valuenow="{progress:.1f}"><span style="width:{progress:.1f}%"></span></div>
    </div>"""


def render_intro(section: str) -> str:
    eyebrow, title, description = PAGE_INFO[section]
    return (f'<div class="peims-section"><div class="peims-section-kicker">{escape(eyebrow)}</div>'
            f'<div class="peims-section-title">{escape(title)}</div>'
            f'<div class="peims-section-text">{escape(description)}</div></div>')


def render_safety() -> str:
    return ("<div class='peims-safety'><strong>DEMONSTRATION DATA</strong>"
            "<span>Independent portfolio prototype. No Newmont integration, live project feed, "
            "shared database, or approved engineering outputs. Edits remain session-only.</span></div>")


def render_footer() -> str:
    return ("<div class='peims-footer'>PEIMS UI 0.5.3 · Fictional engineering project portfolio · "
            "Figures require professional verification · Public demo data is not persistent</div>")
