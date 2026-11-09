# PEIMS v0.5 — Persistent workspace and multiuser API foundation

**Scope:** source code for a separately hosted authenticated API; **not yet connected to the public Streamlit demo**.

## Additions

- Database-backed **action items** with owners, due dates, priorities and status; project-scoped create, list and update endpoints.
- Database-backed **engineering document register** (reference, title, revision and workflow status). **No actual file contents** are uploaded or stored.
- Manager-only **project membership management**: add, list, change roles and revoke. Viewer read-only; engineer edits operations; manager controls membership and financial/audit endpoints. All authority is based on stored membership and a validated OIDC access token.
- **Optimistic version checks** and `409 Conflict` for stale updates; member revocations require a matching version and no remaining assigned action items. Own role/membership changes are blocked through HTTP, and the final manager is protected.
- **Metadata-only audit events** committed atomically with records. No commercial terms, files or full sensitive contents are copied into the audit table.
- Workspace summary endpoint for counts of action and document states, project scoped.
- `/readyz` DB connectivity check (503 when not configured) distinct from `/healthz` liveness.
- Alembic migration `0002_workspace` plus disposable database upgrade/downgrade tests; trusted CLI now requires operator attribution.

## Compatibility

- Existing public demonstration dashboard, data, visualisations and workflows remain functional and **session-only**. The app sidebar now reads v0.5, but **has not gained persistent storage or secure sign-in**.
- Static GitHub Pages preview remains frozen.
- Existing enterprise v0.4 endpoints and test cases remain intact.

## Not yet delivered

- No managed PostgreSQL instance, IdP registration, API DNS/TLS ingress, backend hosting, real account login, database RLS, enterprise DLP or external integration.
- SQLite tests show persistence/permission logic, **not** proof that real PostgreSQL migration, backup/restore, or actual OIDC SSO is deployed.
- No live authenticated browser console for the enterprise API; v0.6 can add that after staging infrastructure is approved.
- No Newmont approval or access to company data.

See `ENTERPRISE_SETUP.md`, `SECURITY.md` and `STAGING_ACCEPTANCE.md` before considering real use.
