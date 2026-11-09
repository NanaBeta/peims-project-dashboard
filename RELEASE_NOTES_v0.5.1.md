# PEIMS v0.5.1 — Analytical Visualization Upgrade

## User outcome
The charts now support real project-controls questions rather than decorative generic graphs. The public Streamlit demo gains an Analytics Studio with work-package owner filtering.

## New and improved analyses
- Executive progress S-curve — weekly reported progress versus historical baseline, with latest recorded gap; no invented forecast.
- Schedule-variance dumbbells — actual and planned completion with delay severity, owners and activity IDs.
- Dependency CPM timeline — modelled activity bars and zero-float paths (not a P6 replacement).
- Cost variance waterfall — recorded AC to EV via CV, with transparent reconciliation.
- Cost/schedule exposure scatter — per-activity progress gap versus cost variance; bubble size indicates baseline budget.
- Procurement exposure scatter — PO expected date versus value, with overdue/critical severity; identifies suppliers.
- Risk heat map — background reflects score P×I, while cells show how many *open* risks fall there.
- Analytics Studio — owner-level drill-down with derived metrics and control register.

## Technical notes
- Added pure Plotly chart functions in `visuals.py` with no external model or API calls.
- Added deterministic chart tests to validate data scoping and plot semantics.
- Improved demo styling and explanatory legends/metric caveats.
- Streamlit integration tests run in CI; local tests skip if Streamlit is unavailable.
- This version does **not** introduce authentication, live persistence, model-based forecasts, or validated P6/SAP equivalence.
- The standalone static `index.html` is a simpler legacy preview; the full analytics experience is in the Streamlit app.
