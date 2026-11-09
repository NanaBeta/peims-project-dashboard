# PEIMS v0.5.2 — Interface & Navigation Refresh

**Scope:** Public fictional-data Streamlit demo only. The separate v0.5 enterprise API is unchanged and remains undeployed.

## What's different

- Replaced the crowded nine-section top-tab ribbon with a **persistent sidebar workspace menu**. Each section renders only when selected; heavy charts in other sections do not run on each interaction.
- Added a **consistent project identity header** with the project type, location, snapshot date, activity progress, linear baseline, and progress gap. This is descriptive project reporting, not a live feed.
- Added an **exception-category indicator** (slippage over five percentage points, high risks, late POs, overdue actions). It counts types of existing exceptions, not distinct issues, and does not claim to be a calibrated project-health score.
- Improved the styling of management KPI tiles, charts, data tables, alerts, form buttons, page headings, and the sidebar.
- Added **Compact layout** in the sidebar for dense desktop use and responsive sizing on small screens; supports reduced-motion system preferences.
- Added explicit **demo-only and no-company-integration** notices in the interface.
- Centralized all presentation helpers in `ui_shell.py`, keeping engineering analytics and validation untouched.

## Using the refreshed navigation

1. Select one of the two synthetic mining projects at the top of the sidebar.
2. Choose a section under **Workspace**: Command centre, Schedule, Cost control, Procurement, Risks & actions, Analytics studio, Reports, Workflows, or Data studio.
3. Enable **Compact layout** if you prefer smaller dashboard tiles.
4. Use Workflows to edit fictional contractor/RFI/document records, and download a workspace ZIP to keep a demonstration snapshot.

## Verification and limitations

- New pure-Python tests assert navigation metadata, safe HTML escaping, bounded progress rendering, status rules, and responsive styles.
- New Streamlit AppTest coverage navigates every section for both projects, checks compact mode, and tests a CSV import in Data studio.
- **No authentication, multiuser persistence, company data sources, or live integration** has been added to the public app.
- This is a portfolio UX upgrade, not an accessibility-certified or enterprise-ready front end. A manual responsive browser review remains necessary.
