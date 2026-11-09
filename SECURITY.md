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
