# PEIMS v0.5 Security model — staging foundation, not production approval

## Boundaries and current state

1. **Public Streamlit / GitHub Pages demonstrators:** fictional portfolio data only. The public Streamlit app has no shared login, cross-user database or lasting backend audit; ZIP backup is session-managed and is not appropriate for sensitive records.
2. **Enterprise API source:** separately deployable FastAPI, **not deployed**. Routes require an RS256-signed API-audience JWT with validated issuer/exp/iat and an explicitly provisioned project membership. Roles come from the database, not tokens or request bodies.
3. **PostgreSQL:** versioned migrations, unique/check constraints, project_id filtering, metadata-only audit rows, row locks on updates and explicit concurrency versions. **No database-level RLS yet.**
4. **Identity provider:** trusted external issuer must supply suitable access tokens. Identity alone is insufficient: a manager or trusted administrator must explicitly grant project membership.

## v0.5 controls

- Project-scoped viewer/engineer/manager permissions; manager-only membership/finance/audit operations.
- No HTTP project creation or self-registration. Manager cannot change/revoke their own membership through API; manager-role changes and removals guard against leaving a project without a manager.
- Concurrent modification conflicts return 409, including versioned membership revocation. Project parent row locking serializes manager membership changes in PostgreSQL.
- Assigned action owners must be existing project members; member revocation is blocked until actions are reassigned.
- Invalid enums, blank fields, progress outside 0–100, negative financial values, overlong strings and duplicate references are rejected.
- Audit entries contain project ID, identity `sub`, action, record ID, changed-field names and timestamp. They do **not** contain full document text or cost details. **These records are not yet tamper-resistant.**
- `/readyz` answers DB connectivity with a generic 503 on failure. No API endpoint creates demo credentials or silently bypasses JWT validation.

## Required before organizational use

- Deploy an authorized OIDC provider and managed Postgres with verified TLS, backups and tested recovery; never run API on public Streamlit Cloud with company data.
- Perform PostgreSQL-specific migration, locking, integrity and recovery tests; current local tests use SQLite only to exercise application logic.
- Implement and assess DB RLS, dedicated database roles, identity/role lifecycle policies, robust tenant isolation, tamper-resistant audit, credential rotation, rate limits, CORS policy, CSRF protection for future browser sessions, monitoring, retention/deletion and security review.
- Scope any future integration with SAP/P6/Aconex/SharePoint to approved interfaces and information-classification policy.
- No employee, mine plans, HSE, procurement or sensitive engineering data until organizational approval. This is an independent portfolio demonstrator, **not a Newmont product**.

## v0.8 collaborative work-management safeguards

The new API uses project-membership checks on each request, read-only viewers, per-project engineer/manager writes, composite DB keys for task parents/assignees/dependencies, optimistic task versions, and author-bound append-only comments/time logs. The public demo remains unauthenticated and isolated. New comments can contain Markdown or HTML-like text; future clients **must render it as escaped text**, never as trusted HTML. `@mentions` are stored as plain text only. The API does not transmit notifications or attachments. Time entries enforce a 24-hour limit per person **per project** per day, not across all organizations. Production requires approved cross-project workload controls, rate limits, retention/deletion policies, DB RLS assessment, OIDC integration tests, PostgreSQL race tests and a formal privacy/security review.


## v0.8.1 Enterprise console

The private browser client is a same-origin server-mediated application. Raw OIDC tokens remain server-only during sign-in; no passwords, OAuth credentials, or access tokens are written to localStorage, browser cookies, or the database. PostgreSQL stores a SHA-256 session-handle digest; the browser holds a random Secure/HttpOnly `__Host-` cookie. Every project action passes existing membership and role checks, and state mutations require a CSRF header. The front end renders untrusted project text via `textContent`, and responses apply CSP/anti-framing/no-sniff protections. A professional security review, deployment controls, centralized logout integration, rate limiting, retention and infrastructure hardening remain mandatory for production.
