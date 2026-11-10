# PEIMS v0.7 — Work Management foundation

## Delivered
- Task register with assignment, status, priority, due date, completion, estimated hours and notes; project-scoped unique IDs.
- Subtask parent links (cycle-checked) and zero-duration milestones.
- One authoritative session task dataset rendered as Kanban-style board, list, task timeline and due-date calendar. Board uses edit controls, **not drag and drop**.
- Finish-to-start dependencies with whole-day nonnegative lag, cycle checks, and an *illustrative* CPM calculation using calendar days (no resource leveling or approved rebaselining).
- Weekly estimated workload and adjustable owner capacity. This is not verified utilization.
- Manual time records, a session timer and time-log register. Timer is active only while the session exists and only logs upon Stop; no background tracking or payroll/billing status.
- Safe rule builder: status transition → priority setting within the selected project. No external notifications or approvals.
- Project-scoped ZIP export/import of work management (tasks, links, time entries, rules, capacities), validated before replacing only the selected project's data.
- New Home action and navigation page. Command centre includes task counts and logged time indicators.

## Important limitations
- **Fictional sample records only**; browser-session state is not a shared database. Project work ZIP export is required to preserve edits between sessions.
- New task records are *separate from* the authoritative activity schedule, project costs and baseline Gantt. Seeded tasks include linked activity IDs, but editing tasks never silently rewrites engineering baselines.
- No multiuser permissions, authenticated time records, guest access, comments/@mentions, documents/attachments, integrations, SOC 2/GDPR certification, drag-and-drop, calendar working days, automatic re-scheduling or AI predictions in this release.
- Rule actions limited to setting priority; no mail/webhook delivery.

## Next architecture work
1. Deploy authenticated enterprise backend and durable organization/project task tables, version checks and audit trail.
2. Add comments, approvals, attachments and protected guest roles.
3. Add notifications and safe automation job processing plus trusted integrations.
4. Add resource calendars, baseline versioning, schedule constraint engine and dependable AI-assist built on real historical data.
