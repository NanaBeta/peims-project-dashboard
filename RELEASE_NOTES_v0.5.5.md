# PEIMS v0.5.5 — Home & guided workspaces

This is an interaction redesign, **not** a production authentication/database release.

## User-visible improvements

- Home is the default first page with a welcoming project card, completion progress versus a modeled baseline, six large navigation choices and a small prioritized action list.
- `Manage schedule` opens a focused activities list. Selecting an activity opens a dedicated detail view, including an optional session-only progress editor. `← All activities` and `← Home` return to their respective levels.
- Cost control, Procurement and Risks & actions now open a concise working view. A separate **Analysis** choice reveals existing advanced charts and registers.
- `Open documents` opens a dedicated metadata directory; click a drawing to view its revision and status. Metadata editing is still available in that workspace.
- Existing Analytics studio, Command centre, Reports, Workflows, Data studio, existing models and exports are preserved.
- Light/Dark/System appearance continues through Streamlit's native Appearance settings. The small-screen layout stacks the Home cards.

## Honest limitations

- No enterprise login, shared database, live procurement feed or approved construction calculation is attached to the public demonstration.
- The new `Home` and record detail views use real fictional CSV samples. The descriptive statuses/metrics are tied to snapshot data; they are not predictive AI.
- Local testing: 65 Python tests passed, 1 Streamlit-only suite skipped because Streamlit is not installed in the container. GitHub Actions integration still needs to run after code is pushed.
