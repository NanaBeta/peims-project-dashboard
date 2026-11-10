# PEIMS professional PM feature matrix — after v0.7

| # | Capability | State | Scope / next step |
|---|---|---|---|
| 1 | Tasks and subtasks | **Demo implemented** | Assign, prioritize, mark progress; project isolation. Durable enterprise storage still pending. |
| 2 | List / Kanban / Gantt / Calendar | **Demo implemented** | One task dataset across work-management views. Separate activity baseline Gantt. No drag/drop. |
| 3 | Dependencies / Milestones / CPM | **Partial** | Finish-to-start, nonnegative lag, cycle checks, calendar-day CPM; no working calendars or approved rebaselines. |
| 4 | Resource management | **Partial** | Estimated remaining-hour workload and capacity warnings; no assignments by role, leveling, leave calendars. |
| 5 | Time tracking | **Partial** | Manual time log and foreground session timer; no authenticated or payable timesheets. |
| 6 | Collaboration | **Pending** | Real-time multiuser comments/mentions/files after enterprise authentication and storage. |
| 7 | Automation | **Partial** | User-configured status-to-priority rules; no external actions or notification jobs. |
| 8 | Reporting | **Partial** | Existing engineering KPIs plus tasks, overdue, completion, logged hours; no real task-status historical burndown. |
| 9 | Integrations & API | **Foundation only** | Separate FastAPI architecture; Slack/Teams/M365 integration not deployed. |
| 10 | Custom fields & templates | **Pending** | Data model versioning, field-type policies and project templates. |
| 11 | Budget tracking | **Existing demo** | Project BAC/EV/AC/CPI, forecasts and costs remain separate from task-hour estimates. |
| 12 | Security | **Foundation only** | Enterprise RBAC/OIDC source, org directories; no production compliance or public demo authentication. |
| 13 | Mobile | **Partial** | Responsive Streamlit, not offline native mobile. |
| 14 | Guest/client access | **Pending** | Project-scoped external identity and access approvals. |
| 15 | AI-assisted insights | **Pending** | Rule-based flags are **not** AI predictions. Historical, consented data and evaluation needed. |
