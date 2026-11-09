# PEIMS v0.5 — staging acceptance checklist

The public sample-data Streamlit site is **not** a safe place for company data. Perform the following in a separate, access-controlled staging environment with wholly fictional records. Do not connect Newmont services without written authorization.

## Infrastructure and operational proof

- [ ] Provision isolated managed PostgreSQL with TLS `verify-full`, minimal credentials, backups, backup retention, network rules, and an audit record of who manages it.
- [ ] Register a separate API audience/client at an approved OIDC provider, configure JWKS URL, issuer and audience. Verify signature, expiry, audience, user subject, and key rotation. **Never treat an ID token as an API authorization token.**
- [ ] Deploy FastAPI through HTTPS with allowed origins, rate limits, request-body limits, safe reverse-proxy headers, and centralized logging. Never expose DB or CLI to the internet.
- [ ] Run Alembic migrations `0001_initial`, `0002_workspace` and verify current revision. Rehearse restore from backup into an isolated second instance before changing schema in production.
- [ ] Confirm `/healthz` = 200 when process is alive; `/readyz` = 200 only when DB works, 503 when DB is unreachable. Neither endpoint grants access to project records.
- [ ] Provision a fictional project and first manager through the **trusted terminal** only using `--actor`; never through public self-registration.

## Authorization and data integrity

- [ ] An unauthenticated request to `/v1/projects` returns 401; invalid or expired API JWT returns 401; a valid token with no project membership sees an empty project list.
- [ ] A viewer may read only their own project's operational records and workspace summary; viewer cannot write or view finance, membership or audit routes.
- [ ] An engineer can manage own-project actions, document metadata, activities and RFIs, but cannot promote themselves or view manager-only finance/audit data.
- [ ] A manager can add/change/revoke team members, but cannot revoke themselves via API; outstanding assigned actions prevent a member's removal.
- [ ] Requests using other project IDs or item IDs return 404 without exposing foreign records.
- [ ] Duplicate action/document identifiers return 409; stale `expected_version` updates or member revocations return 409; audit metadata and updates commit/rollback together.
- [ ] Confirm process restart and two separate authenticated clients see the same updates from PostgreSQL; reload the dashboard/client between edits and confirm conflicts are visible.
- [ ] Test concurrent writes across real PostgreSQL sessions and verify project-row locking in membership changes.

## Engineering and security governance

- [ ] Collect representative staging metrics: request latency, errors, DB connection counts and storage volume.
- [ ] Validate backup recovery, least-privilege DB roles, credential/key rotation, deletion/retention, RLS feasibility, network scanning, security testing, CSRF/CORS policies for the eventual browser client and operator account recovery.
- [ ] Obtain organizational approval before integrating SAP/P6/Aconex/SharePoint or ingesting sensitive mine, HSE, employee or financial records.

**Release gate:** Only after the above checks should an authenticated browser UI use this API; the public PEIMS demo must remain isolated.
