# PEIMS v0.8.1 — Authenticated Enterprise Console (source release)

**Status: implemented and locally tested, not deployed.** This release adds an authenticated browser interface to the private FastAPI enterprise service. It **does not** activate persistent storage in the public Streamlit demonstration. Do not place confidential organizational data in the public demo.

## What is implemented

- A separate `/console/` interface, hosted on **the same origin** as the protected FastAPI service.
- Confidential-client OpenID Connect sign-in using authorization code + PKCE, random state and nonce, exact issuer/audience verification, and server-side token exchange.
- Secure, HttpOnly, SameSite=Lax `__Host-` session cookies. The database holds a SHA-256 hash of a random session ID, verified user subject, and expiry; **OAuth tokens are never stored in browser JavaScript or the session table**.
- CSRF tokens derived server-side, checked on every cookie-authenticated mutation, plus explicit origin checking. HTTPS-only configuration and short session lifetimes.
- Project selection restricted to the authenticated principal's existing membership; role-based controls use the v0.8 service handlers and database authorization checks **on every request**, not merely disabled buttons.
- Connected Home / task board / table / planned timeline / deadline calendar, task create/edit, dependent-task links, comments and signed time entries. Version conflicts return `409` with a reload instruction.
- New `0005_console_sessions` database migration and security-focused tests. Static browser assets have no runtime dependency on third-party CDNs.

## What is *not* implemented or claimed

- No managed PostgreSQL, identity provider, DNS, TLS certificate, or production deployment was provisioned.
- No automatic migration from the public Streamlit session data to enterprise work items. A formal, consented import is a future project.
- No automatic background push notifications or real-time subscriptions; click Refresh to see another person's changes.
- No organization directory administration, document uploads, Teams/SharePoint integration, or approvals in this console yet.
- No audit-compliance certification, SOC 2 attestation, GDPR compliance guarantee, or security assessment has been obtained.
- The task timeline does not constitute a Primavera P6 approved or revision-controlled schedule.

## Testing and safeguards

- Server/API tests exercise OIDC nonce/audience/signature validation with a disposable local test identity provider, project membership and viewer permissions, CSRF/origin checks, persistent task/comment/time records, optimistic-version conflicts, session expiry, tamper resistance and logout.
- Alembic revision tested against disposable SQLite for schema correctness; PostgreSQL staging migration, concurrency and restore tests remain release gates.
- Browser interaction smoke tests (mock records) at 390, 768 and 1440 pixels check Home, board, list, timeline, calendar and details without horizontal overflow or JavaScript exceptions.
- Configure secrets only through an authorized secrets manager. Never commit token examples or use mock identities outside tests.

See [Enterprise console deployment](ENTERPRISE_CONSOLE_v081.md), [Enterprise setup](ENTERPRISE_SETUP.md), and [Staging acceptance](STAGING_ACCEPTANCE.md).
