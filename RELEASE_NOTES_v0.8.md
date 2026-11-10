# PEIMS v0.8 — persistent work-management API (staging foundation)

**Release scope:** independent enterprise backend source and database migration. The public Streamlit/GitHub Pages demos **remain fictional and session-only**; this is **not** a deployed multiuser service.

## Implemented

- `0004_work_management` Alembic schema upgrade: `work_items`, `work_dependencies`, `work_time_entries`, `work_comments`.
- Project-scoped task and subtask/milestone create, list, retrieve, and version-checked update operations. Unique project references and bounded fields are enforced by validation and database constraints.
- Status, priority, assignee, date, estimate, progress and parent validation. Subtasks require an existing task in their own project. Milestones have a single date and zero estimated hours.
- Typed finish-to-start dependency endpoints with cycle checks. The PostgreSQL implementation locks the project row to serialize changes to the dependency graph. No critical-path recalculation or calendar optimization is claimed.
- Append-only time entries and task comments. The author is taken from the verified API access-token subject, never from client text. Time log limit: at most 24 hours per person **per project per date**. Comments do not send @mention alerts.
- Project roles: viewers read, engineers/managers mutate. Task assignees must be a current **engineer or manager member of that project**. Revoking their membership requires reassigning tasks.
- Updates check `expected_version` and return HTTP 409 for stale records. Audit metadata stores actor, event type, work-item ID and field names, atomically committed with the change.
- Database composite foreign keys prevent cross-project dependencies, subtask parents, and assignees, even if application-layer validation is bypassed.
- Project-scoped server summary: total, open, overdue, milestones, logged time. The summary is a live aggregation of stored work records, **not** an approved engineering baseline.

## Still not implemented / deployment gate

- No real managed PostgreSQL service, identity-provider tenant, DNS/HTTPS ingress, enterprise user provisioning or browser OIDC client has been configured in this release.
- The public Streamlit Work Management page continues to use session data, with optional ZIP backup/restore. It is **not** connected to these enterprise endpoints. No automatic import or synchronization of pre-existing demo tasks occurs.
- No real-time WebSockets, push/email notifications, @mention dispatch, file attachments, invitation flows, guest identities, RLS, native mobile offline mode or commercial timesheet approvals.
- No production certification, SOC 2 attestation or GDPR compliance claim. Audit metadata is not tamper resistant.
- The 0004 migration is tested structurally with SQLite and enterprise API tests use a file-backed SQLite substitute. **PostgreSQL staging rehearsal, two live OIDC users, concurrency/locking tests and backup-restore verification are required** before deployment.

## Developer validation

```bash
python -m pip install -r requirements.txt -r requirements-api.txt pytest
python -m pytest tests/ -q
python -m compileall -q enterprise/
```

Apply Alembic migrations only to an approved, backed-up PostgreSQL staging instance. Do not use `Base.metadata.create_all` on a real deployment; that helper appears only in isolated test fixtures.

See [enterprise setup](ENTERPRISE_SETUP.md) and [staging acceptance](STAGING_ACCEPTANCE.md).
