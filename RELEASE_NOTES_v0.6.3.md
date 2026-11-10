# PEIMS v0.6.3 — Approved organization directory (backend foundation)

**Scope:** Separate OIDC-protected FastAPI/SQLAlchemy/Alembic enterprise backend. Public Streamlit app **still uses project-only smart suggestions** and does not communicate with the enterprise API.

- New isolated `Organization`, `OrganizationMember`, `DirectoryEntry` and `OrganizationAuditEvent` models.
- Versioned Alembic migration `0003_organization_directory`: upgrades preexisting projects to unlinked and directory-disabled; keeps existing data intact.
- New org-level provisioning, member management, review workflow, audit and project opt-in endpoints.
- Fail-closed tenant creation; only allowlisted, verified OIDC `sub` claims in `PEIMS_ORG_BOOTSTRAP_SUBS` can create an organization.
- Approved-only filtered suggestions: requires signed API token, both project and org memberships, linked matching tenant and opt-in. Local fallback is project-only.
- Zero automatic promotion of project entries to the organization directory. Two independent audit streams record org and project changes.
- Explicit protections against duplicate entry names (case-insensitive), invalid approval transitions, stale version changes, unapproved values, organization switching and self-admin revocation.
- Tests cover CRUD, tenant isolation, approval-only responses, member revocation, legacy-project defaults and migration downgrade in disposable SQLite.

**Limitations:** Enterprise API is not deployed. No organization directory UI is connected to Streamlit; no real tenant data was provisioned. No full PostgreSQL migration rehearsal, penetration testing or production authentication integration has been performed.
