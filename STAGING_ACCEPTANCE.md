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

## v0.8 work-management pre-deployment gates

- [ ] Apply and rehearse `0004_work_management` in a disposable PostgreSQL staging database, verify foreign keys, indexes, and safe data-preserving migration from the prior revision. Never downgrade a database containing production work records.
- [ ] Confirm two independently signed-in authorized users see durable task changes after service restart, and a third nonmember sees only a 404.
- [ ] Confirm API OIDC issuer/audience/expiry verification and role checks across create, edit, comments and time endpoints. No token pasted into a public frontend.
- [ ] Race two task updates with the same expected version; one must return 409. Race opposing dependency inserts; no cycles may persist.
- [ ] Check task assignee membership integrity, revocation/reassignment, cross-project composite FKs, 24-hour per-project time caps and audit consistency on transaction rollback.
- [ ] Validate time-log/comment retention, audit export policy, approved content rendering, request-size limits, monitoring and backup restore from a separate instance.
- [ ] Do not claim real-time collaboration: add authenticated frontend, notifications and tenant RBAC/RLS review first.


## v0.8.1 enterprise console release gates

- [ ] Verify the separate confidential OIDC client, exact callback URI, state/PKCE/nonce, RS256 issuer/audience/expiry, JWKS rotation, invalid-token handling, and trusted `sub` provisioning with two real test accounts.
- [ ] Verify encrypted **HTTPS** transport, cookies (`__Host-`, Secure, HttpOnly, SameSite), HSTS at the edge, reverse proxy trust and secure session key storage / rotation.
- [ ] Rehearse `0005_console_sessions` migration and backup restoration on isolated managed **PostgreSQL**; confirm existing tasks persist and migration doesn't touch the public Streamlit demo.
- [ ] Verify session expiry, logout invalidation, replay/missing-cookie rejection, CSRF/origin checks, and disabled/revoked organizational identities with defined signout/revocation policy.
- [ ] Check member permissions, cross-project 404 isolation, edits with 409 optimistic conflict, author-attributed comments/time logs, audit retention, rate limits and application firewall rules.
- [ ] Run multi-device/mobile accessibility, sensitive-data logging inspection, retained session cleanup, SSO failure recovery, and user-acceptance tests.
- [ ] Obtain organizational security approval before processing confidential customer information. No SOC 2/GDPR certification is implied by this source release.
