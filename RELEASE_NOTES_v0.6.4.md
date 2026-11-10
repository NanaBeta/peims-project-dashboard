# PEIMS v0.6.4 — Visible Gantt and project schedule

## Interface
- **Home:** A compact six-activity timeline prioritizing behind-schedule and active work, with a link to the full Gantt.
- **Command centre:** The full Gantt before the existing project S-curve.
- **Planning & schedule:** A **Gantt** default view, owner/status filters, date zoom, selected-activity details and CSV export. The previous Activities and Analysis tabs—including limited CPM—remain available.
- Current validated project records power every chart; session edits and new activities appear on the next rerun. Narrow-axis labels are shortened and full activity details are provided on hover.

## Important data constraints
- Grey bars show start/finish dates from the current planned activity register, not an approved Primavera baseline version.
- Coloured fills are reported physical completion *proportions on the planned windows*, NOT actual work date intervals.
- Dashed vertical line is the project's reporting snapshot, not the viewer's real-world date.
- Actual dates, approved revised baselines, working calendars, resource constraints, editable dependency lines and forecasting remain future work.
- Fictional demo only; no Newmont, Asana or P6 integrations, no persistent multiuser workspace.

## Verification
- Local Python: 120 passed, 1 Streamlit-only suite skipped.
- Static preview: passed 12 module/project combinations and 2 report handlers.
- Plotly rendered offline without errors or overflow at 390, 768 and 1280 px.
- GitHub CI runs full Streamlit smoke and Gantt navigation tests before merge.

## Next features
Task Kanban board, project calendar/milestones, dependency editing, approved baseline versioning, saved views and enterprise persistence are subsequent releases; they are not included here.
