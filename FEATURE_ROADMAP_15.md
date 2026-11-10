# PEIMS professional PM feature matrix — v0.8 backend foundation

| # | Capability | State | Scope / next step |
|---|---|---|---|
| 1 | Tasks and subtasks | **Demo implemented** | Assign, prioritize, mark progress; project isolation. Enterprise API/DB schema now implemented but undeployed; demo remains session-only. |
| 2 | List / Kanban / Gantt / Calendar | **Demo implemented** | One task dataset across work-management views. Separate activity baseline Gantt. No drag/drop. |
| 3 | Dependencies / Milestones / CPM | **Partial** | Finish-to-start, nonnegative lag, cycle checks, calendar-day CPM; no working calendars or approved rebaselines. |
| 4 | Resource management | **Partial** | Estimated remaining-hour workload and capacity warnings; no assignments by role, leveling, leave calendars. |
| 5 | Time tracking | **Partial** | Manual time log and foreground session timer; authenticated API time entries in backend; no approved/billable timesheets. |
| 6 | Collaboration | **Pending** | Authenticated append-only task comments in backend; no live UI, notifications or attachments. |
| 7 | Automation | **Partial** | User-configured status-to-priority rules; no external actions or notification jobs. |
| 8 | Reporting | **Partial** | Existing engineering KPIs plus tasks, overdue, completion, logged hours; no real task-status historical burndown. |
| 9 | Integrations & API | **Foundation only** | Expanded project-scoped work-management FastAPI; Slack/Teams/M365 not integrated. |
| 10 | Custom fields & templates | **Pending** | Data model versioning, field-type policies and project templates. |
| 11 | Budget tracking | **Existing demo** | Project BAC/EV/AC/CPI, forecasts and costs remain separate from task-hour estimates. |
| 12 | Security | **Foundation only** | Project RBAC/OIDC, directory code and DB constraints; service not deployed, no compliance attestation. |
| 13 | Mobile | **Partial** | Responsive Streamlit, not offline native mobile. |
| 14 | Guest/client access | **Pending** | Project-scoped external identity and access approvals. |
| 15 | AI-assisted insights | **Pending** | Rule-based flags are **not** AI predictions. Historical, consented data and evaluation needed. |
