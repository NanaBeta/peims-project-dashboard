"""PEIMS public demonstration UI shell.

Presentation-only helpers. No database calls, network requests, access-control claims,
or changes to analytical records are made here.
"""
from __future__ import annotations

from html import escape

NAVIGATION = (
    "Home",
    "Command centre",
    "Schedule",
    "Cost control",
    "Procurement",
    "Risks & actions",
    "Analytics studio",
    "Reports",
    "Documents",
    "Workflows",
    "Data studio",
    "Spreadsheet studio",
    "Work management",
)

NAV_LABELS = {
    "Home": "⌂   Home",
    "Documents": "▦   Documents",
    "Command centre": "◈   Command centre",
    "Schedule": "▤   Planning & schedule",
    "Cost control": "◉   Cost & commercial",
    "Procurement": "▣   Procurement",
    "Risks & actions": "⚑   Risks & actions",
    "Analytics studio": "◫   Analytics studio",
    "Reports": "▧   Reports",
    "Workflows": "▦   Workflows",
    "Data studio": "⚙   Data studio",
    "Spreadsheet studio": "▦   Spreadsheets & BI",
    "Work management": "▤   Tasks & work management",
}

PAGE_INFO = {
    "Home": ("WELCOME", "Home", "Choose a workspace to get started."),
    "Documents": ("ENGINEERING DOCUMENTS", "Documents", "Find and review drawing metadata, revisions and responsible engineers."),
    "Command centre": ("PORTFOLIO INTELLIGENCE", "Command centre", "Monitor performance, exceptions and decisions from one consolidated view."),
    "Schedule": ("PROJECT DELIVERY", "Planning & schedule", "Inspect actual completion, dependencies, criticality and baseline slippage."),
    "Cost control": ("PROJECT COMMERCIAL", "Cost & commercial", "Connect financial performance, earned value and forecast scenarios."),
    "Procurement": ("SUPPLY CHAIN", "Procurement", "Follow overdue deliveries, critical equipment and purchase-order exposure."),
    "Risks & actions": ("ASSURANCE", "Risks & actions", "Prioritize open risks, accountable owners and overdue action items."),
    "Analytics studio": ("PROJECT INTELLIGENCE", "Analytics studio", "Explore cross-discipline project controls with work-package filters."),
    "Reports": ("REPORTING", "Reports", "Generate a traceable draft based on the selected project snapshot."),
    "Workflows": ("ENGINEERING COORDINATION", "Workflows", "Maintain demonstration contractor, RFI and document registers."),
    "Data studio": ("DATA GOVERNANCE", "Data studio", "Inspect sample records and validate session-only data imports."),
    "Spreadsheet studio": ("DATA WORKSPACE", "Spreadsheets & BI", "Edit project registers, exchange Excel workbooks, and create focused analytical views."),
    "Work management": ("PROJECT DELIVERY", "Tasks & work management", "Manage tasks, subtasks and milestones across board, list, calendar and timeline views."),
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
    """Polish only; Streamlit theme tokens own the light/dark palette.

    Do not hard-code dark backgrounds or text: the browser's Streamlit Appearance
    setting switches native tables, input controls and the custom shell together.
    CSS tokens are supplied by Streamlit and update with its native theme.
    """
    density = """
    [data-testid="stMetric"] { padding: .65rem .85rem !important; min-height: 78px; }
    .peims-hero { padding: 1rem 1.2rem !important; }
    """ if compact else ""
    return """<style>
    :root {
      --peims-ink:var(--st-text-color, currentColor);
      --peims-canvas:var(--st-background-color, transparent);
      --peims-surface:var(--st-secondary-background-color, transparent);
      --peims-border:var(--st-border-color, rgba(125,145,165,.26));
      --peims-accent:var(--st-link-color, var(--st-primary-color, #8a611f));
    }
    html,body,[data-testid="stAppViewContainer"] {
      font-family:Inter, ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
    }
    /* Allow the actual Streamlit theme to style native data grids, forms and menus. */
    /* Streamlit supplies the top inset via theme.paddingTop, including
       its toolbar height. Never override .block-container padding-top. */
    .block-container {max-width:1500px;padding-left:1.8rem;padding-right:1.8rem;padding-bottom:3rem;}
    h1,h2,h3 {letter-spacing:-.03em;}
    h1 {font-size:2rem !important;font-weight:750 !important;line-height:1.22 !important;}
    h2 {font-size:1.45rem !important;font-weight:720 !important;}
    h3 {font-size:1.12rem !important;font-weight:680 !important;}
    [data-testid="stSidebar"] > div:first-child {padding-top:1.1rem;}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {gap:.22rem;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
      border-radius:9px;padding:.37rem .55rem;transition:background .15s ease;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
      background:color-mix(in srgb, var(--peims-ink) 7%, transparent);
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"] {
      background:color-mix(in srgb, var(--peims-accent) 14%, transparent);
    }
    [data-testid="stMetric"] {
      background:var(--peims-surface);border:1px solid var(--peims-border);
      border-radius:13px;padding:.95rem 1.08rem;min-height:99px;
    }
    [data-testid="stMetricLabel"] {font-weight:540;font-size:.82rem;}
    [data-testid="stMetricValue"] {letter-spacing:-.04em;font-weight:760;}
    [data-testid="stMetricDelta"] {font-size:.79rem;}
    /* Command centre KPI cards: prevent cropped values when the sidebar is open.
       Scope this grid to the overview only; other charts keep their own layout. */
    .st-key-peims_overview_kpis [data-testid="stHorizontalBlock"] {
      display:grid !important; grid-template-columns:repeat(4,minmax(0,1fr));
      gap:1rem !important; align-items:stretch;
    }
    .st-key-peims_overview_kpis [data-testid="stColumn"] {
      min-width:0 !important; width:100% !important; flex:none !important;
    }
    .st-key-peims_overview_kpis [data-testid="stMetric"] {height:100%;min-width:0;}
    .st-key-peims_overview_kpis [data-testid="stMetricLabel"] p {
      white-space:normal !important; overflow-wrap:anywhere;
      line-height:1.4;
    }
    @media (max-width:1250px) {
      .st-key-peims_overview_kpis [data-testid="stHorizontalBlock"] {
        grid-template-columns:repeat(2,minmax(0,1fr));
      }
    }
    @media (max-width:510px) {
      .st-key-peims_overview_kpis [data-testid="stHorizontalBlock"] {
        grid-template-columns:minmax(0,1fr);
      }
    }
    [data-testid="stPlotlyChart"] {
      background:var(--peims-surface);border:1px solid var(--peims-border);
      border-radius:13px;padding:.4rem .55rem .15rem;
    }
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
      border:1px solid var(--peims-border);border-radius:11px;overflow:hidden;
    }
    [data-testid="stForm"], [data-testid="stExpander"],
    [data-testid="stVerticalBlockBorderWrapper"] {border-radius:12px;}
    [data-testid="stButton"] button,[data-testid="stDownloadButton"] button {
      border-radius:9px;font-weight:600;
    }
    [data-testid="stButton"] button:hover,[data-testid="stDownloadButton"] button:hover {
      border-color:var(--peims-accent);
    }
    [data-testid="stCaptionContainer"] {line-height:1.5;}
    .peims-brand {display:flex;align-items:center;gap:.8rem;padding:.1rem 0 .55rem;}
    .peims-brand-mark {width:41px;height:41px;border-radius:11px;display:grid;place-items:center;
      background:linear-gradient(140deg,#f2ce83,#b47c28);color:#16263b;font-size:17px;font-weight:900;}
    .peims-brand-title {font-size:1.13rem;font-weight:800;letter-spacing:.12em;color:var(--peims-ink);}
    .peims-brand-sub {font-size:.68rem;opacity:.72;letter-spacing:.06em;}
    .peims-sidebar-heading {font-size:.64rem;opacity:.72;letter-spacing:.16em;font-weight:800;margin:1rem 0 .2rem;}
    .peims-sidebar-note {background:var(--peims-surface);border:1px solid var(--peims-border);
       border-radius:10px;padding:.75rem .8rem;font-size:.75rem;line-height:1.5;color:var(--peims-ink);}
    .peims-theme-tip {border-left:3px solid var(--peims-accent);padding:.35rem .65rem;
       font-size:.74rem;line-height:1.5;opacity:.9;margin:.35rem 0 .8rem;}
    .peims-theme-tip strong {color:var(--peims-ink);}
    .peims-hero {padding:1.35rem 1.55rem 1.2rem;
       border:1px solid var(--peims-border);border-radius:18px;
       background:linear-gradient(120deg,
         color-mix(in srgb, var(--peims-accent) 6%, var(--peims-surface)),
         var(--peims-surface) 82%);margin:0 0 .8rem;}
    .peims-hero-top {display:flex;align-items:center;justify-content:space-between;gap:.7rem;flex-wrap:wrap;}
    .peims-eyebrow {font-size:.66rem;color:var(--peims-accent);font-weight:800;letter-spacing:.15em;}
    .peims-badge {display:inline-flex;align-items:center;gap:.4rem;
       border:1px solid var(--peims-border);background:var(--peims-canvas);
       border-radius:99px;padding:.28rem .68rem;color:var(--peims-ink);
       font-size:.72rem;font-weight:700;}
    .peims-badge.warning {border-color:#b77a29;background:color-mix(in srgb,#b77a29 12%,var(--peims-surface));}
    .peims-badge.neutral {border-color:#34887e;background:color-mix(in srgb,#34887e 10%,var(--peims-surface));}
    .peims-hero-title {font-size:clamp(1.4rem,2.1vw,2rem);font-weight:760;
       letter-spacing:-.043em;color:var(--peims-ink);line-height:1.23;margin:.65rem 0 .35rem;}
    .peims-hero-sub {font-size:.82rem;opacity:.8;line-height:1.5;}
    .peims-info-row {display:flex;align-items:center;gap:.45rem;flex-wrap:wrap;margin-top:.66rem;}
    .peims-info-chip {font-size:.72rem;color:var(--peims-ink);
       background:var(--peims-canvas);border:1px solid var(--peims-border);
       border-radius:8px;padding:.26rem .57rem;}
    .peims-info-chip strong {color:var(--peims-ink);}
    .peims-progress-summary {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
       gap:.65rem;margin-top:1rem;}
    .peims-progress-stat {background:var(--peims-canvas);border:1px solid var(--peims-border);
       padding:.65rem .8rem;border-radius:11px;min-width:0;}
    .peims-progress-label {display:block;font-size:.7rem;opacity:.78;line-height:1.25;}
    .peims-progress-value {display:block;margin-top:.25rem;color:var(--peims-ink);
       font-size:clamp(1.1rem,1.65vw,1.55rem);line-height:1.14;font-weight:750;letter-spacing:-.03em;}
    .peims-progress-value.adverse {color:#b55552;}
    .peims-progress-value.favourable {color:#208f85;}
    .peims-progress {position:relative;height:9px;background:color-mix(in srgb,var(--peims-ink) 12%,transparent);
       border-radius:20px;margin-top:.9rem;}
    .peims-progress > span {display:block;height:100%;
       background:linear-gradient(90deg,#a47a31,#218f86);border-radius:20px;}
    .peims-progress-target {position:absolute;top:-4px;bottom:-4px;width:3px;
       background:var(--peims-ink);border-radius:2px;transform:translateX(-50%);}
    .peims-progress-legend {display:flex;gap:1.1rem;align-items:center;flex-wrap:wrap;
       margin-top:.5rem;font-size:.69rem;opacity:.85;}
    .peims-legend-swatch {display:inline-block;width:10px;height:5px;border-radius:4px;
       background:#218f86;margin-right:.35rem;vertical-align:middle;}
    .peims-legend-baseline {display:inline-block;height:10px;width:3px;margin-right:.35rem;
       background:var(--peims-ink);vertical-align:middle;}
    .peims-shortcut-caption {font-size:.71rem;opacity:.75;letter-spacing:.1em;
       font-weight:750;margin:.6rem 0 .3rem;}
    .st-key-peims_shortcuts button {min-height:43px;}
    .peims-safety {display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;
       border-radius:9px;border:1px solid var(--peims-border);
       background:var(--peims-surface);
       padding:.65rem .82rem;color:var(--peims-ink);font-size:.74rem;margin:0 0 1rem;}
    .peims-safety strong {color:var(--peims-accent);letter-spacing:.03em;}
    .peims-section {margin:.3rem 0 1.1rem;}
    .peims-section-kicker {font-size:.68rem;color:var(--peims-accent);
      letter-spacing:.13em;font-weight:800;margin-bottom:.2rem;}
    .peims-section-title {font-size:1.33rem;font-weight:750;color:var(--peims-ink);letter-spacing:-.04em;}
    .peims-section-text {font-size:.85rem;opacity:.78;margin-top:.1rem;}
    .peims-footer {border-top:1px solid var(--peims-border);padding:.9rem 0;
      opacity:.75;font-size:.74rem;line-height:1.6;margin-top:1.15rem;}
    .peims-alert {padding:.76rem .92rem;border-radius:10px;
      border-left:3px solid #b9822d;background:var(--peims-surface);
      color:var(--peims-ink);margin:.5rem 0;font-size:.83rem;line-height:1.5;}
    .peims-alert strong {color:var(--peims-ink);font-size:.8rem;}
    .peims-alert small {display:block;margin-top:.24rem;opacity:.78;}
    /* Navigation-first experience: generous but functional, with one task per page. */
    .peims-welcome {display:flex;align-items:center;justify-content:space-between;
      gap:2.2rem;flex-wrap:wrap;padding:2rem 2.1rem;border:1px solid var(--peims-border);
      background:var(--peims-surface);border-radius:20px;margin:0 0 1.6rem;}
    .peims-welcome-copy {flex:2 1 300px;min-width:0;}
    .peims-welcome h1 {font-size:clamp(1.55rem,2.7vw,2.3rem) !important;
      margin:.55rem 0 .65rem;line-height:1.2;}
    .peims-welcome p {max-width:48rem;line-height:1.65;font-size:.94rem;opacity:.8;margin:0;}
    .peims-welcome-progress {flex:1 1 205px;max-width:330px;min-width:190px;
      padding:1.1rem 1.3rem;border-radius:14px;border:1px solid var(--peims-border);
      background:var(--peims-canvas);}
    .peims-welcome-progress strong {display:block;font-size:2.05rem;letter-spacing:-.04em;
      line-height:1.4;font-weight:750;color:var(--peims-ink);}
    .peims-welcome-caption {font-size:.71rem;opacity:.75;line-height:1.55;margin-top:.6rem;}
    .peims-home-label {font-size:1.15rem;font-weight:740;margin:1.35rem 0 .22rem;}
    .peims-home-sub {font-size:.86rem;opacity:.7;margin:0 0 1.2rem;}
    [class*="st-key-home_card_"] {padding:1.1rem!important;border-radius:16px!important;
      border:1px solid var(--peims-border)!important;background:var(--peims-surface);}
    [class*="st-key-home_card_"] [data-testid="stButton"] button {
      justify-content:space-between;min-height:45px;font-weight:720;
      background:color-mix(in srgb,var(--peims-accent) 9%,transparent);
      border-color:color-mix(in srgb,var(--peims-accent) 26%,var(--peims-border));
    }
    [class*="st-key-home_card_"] [data-testid="stButton"] button:hover {
      background:color-mix(in srgb,var(--peims-accent) 15%,transparent);}
    .peims-card-icon {font-size:1.4rem;line-height:1.25;margin-bottom:.5rem;}
    .peims-card-info {font-size:.82rem;line-height:1.5;opacity:.73;min-height:2.3rem;}
    .peims-card-count {font-size:.72rem;font-weight:650;letter-spacing:.02em;
      color:var(--peims-accent);margin-top:.4rem;}
    .peims-breadcrumb {font-size:.77rem;letter-spacing:.03em;opacity:.65;line-height:1.6;}
    .peims-detail-title {font-size:1.35rem;font-weight:750;line-height:1.3;margin:.3rem 0 .65rem;}
    [class*="st-key-peims_record_"] [data-testid="stButton"] button {
      white-space:normal;text-align:left;justify-content:flex-start;min-height:56px;
      line-height:1.4;font-weight:560;border-color:var(--peims-border);
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {min-height:39px;}
    @media (max-width:800px) {
      .block-container{padding-left:.85rem;padding-right:.85rem;padding-bottom:2.3rem;}
      .peims-welcome {padding:1.1rem;gap:.8rem;margin-bottom:1rem;}
      .peims-welcome-progress {max-width:none;flex-basis:100%;min-width:0;}
      .peims-welcome h1 {font-size:1.55rem!important;}
      [class*="st-key-home_card_"] {padding:.75rem!important;}
      .peims-hero{padding:.95rem .9rem;}
      .peims-hero-title{font-size:1.36rem;}
      .peims-progress-summary{gap:.4rem;}
      .peims-progress-stat{padding:.57rem .6rem;}
      .peims-progress-value{font-size:1.1rem;}
      [data-testid="stMetric"] {min-height:81px;padding:.68rem .75rem;}
      .peims-info-chip {font-size:.69rem;}
      .st-key-peims_shortcuts [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.4rem;}
      .st-key-peims_shortcuts [data-testid="stColumn"]{flex:1 1 calc(50% - .4rem)!important;min-width:125px!important;}
    }
    @media (max-width:420px) {
      .peims-progress-summary{grid-template-columns:repeat(2,minmax(0,1fr));}
      .peims-progress-stat:last-child{grid-column:1/-1;}
      .peims-brand-title{font-size:1rem;}
      .peims-hero-sub{font-size:.75rem;}
    }
    button:focus-visible, [role="radio"]:focus-visible, a:focus-visible {
      outline:2px solid var(--peims-accent)!important;outline-offset:3px;
    }
    @media (prefers-reduced-motion: reduce) {
      * {scroll-behavior:auto !important;transition:none !important;}
    }
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
        <span class="peims-info-chip">Reporting snapshot <strong>{date}</strong></span>
      </div>
      <div class="peims-progress-summary" aria-label="Project performance summary">
        <div class="peims-progress-stat"><span class="peims-progress-label">Recorded completion</span>
          <strong class="peims-progress-value">{progress:.1f}%</strong></div>
        <div class="peims-progress-stat"><span class="peims-progress-label">Linear baseline</span>
          <strong class="peims-progress-value">{planned:.1f}%</strong></div>
        <div class="peims-progress-stat"><span class="peims-progress-label">Progress gap</span>
          <strong class="peims-progress-value {'adverse' if gap < 0 else 'favourable'}">{gap:+.1f} pp</strong></div>
      </div>
      <div class="peims-progress" role="progressbar" aria-label="Recorded physical progress"
        aria-valuemin="0" aria-valuemax="100" aria-valuenow="{progress:.1f}">
        <span style="width:{progress:.1f}%"></span>
        <i class="peims-progress-target" aria-hidden="true" style="left:{max(0.,min(100.,planned)):.1f}%"></i>
      </div>
      <div class="peims-progress-legend"><span><i class="peims-legend-swatch"></i>Actual progress</span>
        <span><i class="peims-legend-baseline"></i>Linear baseline marker</span></div>
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
    return ("<div class='peims-footer'>PEIMS UI 0.5.4 · Fictional engineering project portfolio · "
            "Figures require professional verification · Public demo data is not persistent</div>")
