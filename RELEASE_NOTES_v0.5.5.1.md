# PEIMS v0.5.5.1 — Navigation and KPI layout correction

- Reload the pure UI module during Streamlit hot-restarts to prevent stale navigation choices.
- Migrate existing sessions to the Home page once when entering this release.
- Treat unknown navigation targets as a safe Home recovery rather than a crashing exception.
- Replace the cramped four-across Command centre KPIs with a responsive four/two/one-column grid and shorter, readable labels.
- All project records remain fictional and edits remain session-scoped.

Note: A fresh Streamlit Cloud reboot is recommended after deployment to clear any older Python worker imports.
