# PEIMS v0.5.4 — Mobile-first workspace polish

This release improves the public, fictional Streamlit demo interface without changing financial calculations, the data model, or the enterprise backend.

## Updated UX

- Reorganized project header: separates project identity from three clear performance indicators—recorded physical completion, the assumed linear baseline, and the percentage-point gap.
- The progress track includes a baseline marker and a visible legend. This reduces ambiguity: the bar represents **actual completion**, and the marker represents the **modelled linear baseline**. It is not a formally approved baseline.
- Overview quick-access actions jump directly to Schedule, Cost control, Procurement and Reports using the existing Streamlit sidebar selection state.
- Collapsed Appearance and Workspace Information panels keep the sidebar shorter, especially on phones. Light, Dark, and System remain the **native Streamlit settings**, not custom CSS approximations.
- Responsive behavior for 800px and 420px widths, larger quick-action hit targets, visible keyboard focus outlines, and reduced-motion support.
- Existing project-control charts, datasets, workflow state, and downloadable reports remain unchanged.

## Safety and scope

All data is synthetic. The enterprise API is not deployed or connected to the public Streamlit demo. This is not Newmont-authorized software.

## Verification

`PYTHONPATH=. python -m pytest tests/ -q` plus `node scripts/test_preview.js`, compile check, and cloud AppTest via GitHub Actions. Cloud tests should pass before merge. A screenshot-level mobile browser review is still recommended.
