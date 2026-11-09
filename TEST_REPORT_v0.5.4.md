# PEIMS v0.5.4 — UI release verification

## Local checks (2026-11-09)

- `PYTHONPATH=. python -m pytest tests/ -q` — **60 passed, 1 skipped**. The skipped module depends on Streamlit; GitHub CI installs it and runs AppTest.
- `node scripts/test_preview.js` — **12 module/project checks and 2 download-handler checks passed**.
- `python -m compileall -q app.py ui_shell.py` — passed.
- Playwright-rendered component design checks at 390×844 and 1440×900 for Light and Dark — no horizontal overflow. This tests the custom project header/section intro only, not the complete hosted Streamlit UI.

## Changes verified

- Hero separates real synthetic completion from assumed linear baseline, with percentage-point gap and semantic legend.
- Quick Access shortcuts update the existing sidebar workspace navigation state.
- Native Light / Dark / System appearance remains unchanged.
- Theme tokens are not pinned to a single appearance.
- Page navigation, financial computations, and enterprise security remain unchanged.

## Release gate

Require GitHub CI AppTest success on the feature branch before merge to main. A real browser check of the hosted mobile and desktop app is still required after merge.
